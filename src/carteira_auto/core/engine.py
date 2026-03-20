"""DAG Pipeline Engine — resolve dependências via topological sort (Kahn's Algorithm)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Any

from carteira_auto.utils import get_logger
from carteira_auto.utils.decorators import log_execution, timer

logger = get_logger(__name__)


# ============================================================================
# EXCEÇÕES
# ============================================================================


class CycleDetectedError(Exception):
    """Ciclo detectado no grafo de dependências."""


class MissingDependencyError(Exception):
    """Node depende de outro que não está registrado."""


class NodeNotFoundError(Exception):
    """Node não encontrado no engine."""


# ============================================================================
# CONTEXTO
# ============================================================================


class PipelineContext(dict):
    """Container para dados compartilhados entre nodes.

    É um dict com métodos tipados de conveniência.
    Cada node lê do contexto o que precisa e escreve o que produziu.
    """

    def get_typed(self, key: str, expected_type: type) -> Any:
        """Obtém valor do contexto com verificação de tipo."""
        value = self.get(key)
        if value is not None and not isinstance(value, expected_type):
            raise TypeError(
                f"Esperado {expected_type.__name__} para '{key}', "
                f"obteve {type(value).__name__}"
            )
        return value


# ============================================================================
# NODE (bloco do DAG)
# ============================================================================


class Node(ABC):
    """Bloco de execução do DAG.

    Cada node declara:
        - name: identificador único
        - dependencies: lista de nomes dos nodes predecessores
        - run(ctx): executa a lógica e retorna o contexto atualizado
    """

    name: str
    dependencies: list[str] = []

    @abstractmethod
    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Executa a lógica do node.

        Args:
            ctx: Contexto com dados dos nodes anteriores.

        Returns:
            Contexto atualizado com os dados produzidos por este node.
        """

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name='{self.name}', deps={self.dependencies})"
        )


# ============================================================================
# DAG ENGINE
# ============================================================================


class DAGEngine:
    """Engine que registra nodes e resolve dependências via topological sort.

    Usage:
        dag_engine = DAGEngine()
        dag_engine.register(LoadPortfolioNode())
        dag_engine.register(FetchPortfolioPricesNode())
        dag_engine.register(ExportPortfolioPricesNode())

        ctx = dag_engine.run("export_portfolio_prices")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}

    def register(self, node: Node) -> None:
        """Registra um node no engine."""
        if node.name in self._nodes:
            logger.warning(f"Node '{node.name}' já registrado — substituindo")
        self._nodes[node.name] = node
        logger.debug(f"Node registrado: {node}")

    def register_many(self, nodes: list[Node]) -> None:
        """Registra múltiplos nodes de uma vez."""
        for node in nodes:
            self.register(node)

    def get_node(self, name: str) -> Node:
        """Retorna um node pelo nome."""
        if name not in self._nodes:
            raise NodeNotFoundError(f"Node '{name}' não encontrado")
        return self._nodes[name]

    def list_nodes(self) -> list[str]:
        """Lista nomes de todos os nodes registrados."""
        return list(self._nodes.keys())

    def resolve(self, target: str) -> list[Node]:
        """Resolve dependências via topological sort (Kahn's Algorithm).

        Caminha para trás a partir do target coletando dependências transitivas,
        depois ordena topologicamente.

        Args:
            target: Nome do node terminal a executar.

        Returns:
            Lista de nodes na ordem de execução.

        Raises:
            NodeNotFoundError: Node não encontrado.
            MissingDependencyError: Dependência não registrada.
            CycleDetectedError: Ciclo detectado no grafo.
        """
        # 1. Coleta subgrafo relevante (BFS para trás)
        relevant = self._collect_subgraph(target)

        # 2. Calcula in-degrees dentro do subgrafo
        in_degree: dict[str, int] = dict.fromkeys(relevant, 0)
        for name in relevant:
            node = self._nodes[name]
            for dep in node.dependencies:
                if dep in relevant:
                    in_degree[name] += 1

        # 3. Kahn's Algorithm
        queue: deque[str] = deque()
        for name, degree in in_degree.items():
            if degree == 0:
                queue.append(name)

        order: list[Node] = []
        while queue:
            current_name = queue.popleft()
            order.append(self._nodes[current_name])

            # Decrementa in-degree dos dependentes
            for name in relevant:
                node = self._nodes[name]
                if current_name in node.dependencies:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        if len(order) != len(relevant):
            processed = {n.name for n in order}
            remaining = relevant - processed
            raise CycleDetectedError(f"Ciclo detectado envolvendo: {remaining}")

        return order

    def _collect_subgraph(self, target: str) -> set[str]:
        """Coleta todos os nodes necessários para executar o target (BFS reversa)."""
        if target not in self._nodes:
            raise NodeNotFoundError(f"Node '{target}' não encontrado")

        visited: set[str] = set()
        queue: deque[str] = deque([target])

        while queue:
            name = queue.popleft()
            if name in visited:
                continue
            visited.add(name)

            node = self._nodes.get(name)
            if node is None:
                raise MissingDependencyError(f"Dependência '{name}' não registrada")

            for dep in node.dependencies:
                if dep not in visited:
                    queue.append(dep)

        return visited

    def dry_run(self, target: str) -> list[str]:
        """Mostra o plano de execução sem executar.

        Returns:
            Lista de nomes dos nodes na ordem de execução.
        """
        order = self.resolve(target)
        return [node.name for node in order]

    @log_execution
    @timer
    def run(self, target: str, ctx: PipelineContext | None = None) -> PipelineContext:
        """Resolve dependências e executa o pipeline.

        Args:
            target: Nome do node terminal.
            ctx: Contexto inicial (opcional).

        Returns:
            Contexto final com todos os dados produzidos.
        """
        if ctx is None:
            ctx = PipelineContext()

        order = self.resolve(target)

        logger.info(
            f"Executando pipeline '{target}': " f"{' → '.join(n.name for n in order)}"
        )

        for node in order:
            logger.info(f"▶ {node.name}")
            ctx = node.run(ctx)

        logger.info(f"Pipeline '{target}' concluído com sucesso")
        return ctx
