"""Gerenciamento centralizado de caminhos."""

from pathlib import Path
from typing import Optional

from .settings import settings


class PathManager:
    """Gerencia caminhos da aplicação."""
    
    
    def __init__(self):
        self.settings = settings
    
    
    def get_portfolio_file(self, date_str: Optional[str] = None) -> Path:
        """Retorna caminho para arquivo de carteira."""
        if date_str:
            filename = f"carteira_{date_str}.xlsx"
        else:
            from datetime import datetime
            filename = f"carteira_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return self.settings.paths.OUTPUTS_DIR / "portfolios" / filename
    
    
    def get_report_file(self, report_type: str, date_str: Optional[str] = None) -> Path:
        """Retorna caminho para arquivo de relatório."""
        if date_str:
            filename = f"relatorio_{report_type}_{date_str}.md"
        else:
            from datetime import datetime
            filename = f"relatorio_{report_type}_{datetime.now().strftime('%Y%m%d')}.md"
        
        return self.settings.paths.OUTPUTS_DIR / "reports" / filename
    
    
    def ensure_directories(self) -> None:
        """Garante que todos os diretórios necessários existam."""
        directories = [
            self.settings.paths.OUTPUTS_DIR / "portfolios",
            self.settings.paths.OUTPUTS_DIR / "reports",
            self.settings.paths.OUTPUTS_DIR / "logs",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# Instância global do gerenciador de caminhos
paths = PathManager()