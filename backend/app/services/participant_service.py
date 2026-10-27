"""Compatibilidade temporaria.

O antigo servico de participante (documentos, banco e familiares) foi substituido
pela arquitetura de conta global e jornadas independentes. Use:

- ``account_service`` para perfil global, dados bancarios, familiares,
  jornadas e qualificacoes;
- ``document_service`` para documentos genericos;
- ``representative_service`` para vinculos e workflow de escolas;
- ``qualification_service`` para requisitos e emissoes;
- ``participant_directory_service`` para consultas de administracao/clientes.
"""


def __getattr__(name: str):
    raise AttributeError(
        f"participant_service.{name} foi removido; use os servicos de conta global."
    )
