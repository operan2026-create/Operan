# Mapa inicial do projeto OPERAN

Este documento registra apenas o estado informado/analisado inicialmente. Confirme a árvore atual antes de usar nomes de arquivos ou supor que um recurso esteja completo.

## Backend esperado

- `backend/app/main.py`: aplicação FastAPI.
- `backend/app/api/v1/`: rotas versionadas, incluindo auth, organizations, roles, academy, locations, professionals, missions e router.
- `backend/app/core/`: configuração, banco de dados e dependências.
- `backend/app/models/`: modelos de usuário, organização, vínculo, função, Academia, rede territorial e missão.
- `backend/app/schemas/`: contratos Pydantic.
- `backend/app/security/`: JWT, hashing e criptografia.
- `backend/app/services/`: regras de negócio para usuários, organizações, missões, Academia e rede.
- `backend/alembic/`: migrations.

## Frontend esperado

React + TypeScript + Vite, React Router, React Query, Axios, Tailwind CSS v4 e lucide. Foram descritas páginas administrativas e páginas ligadas à Academia, cadastro de colaboradores, rede, locais e missões. Inspecione o roteador e os layouts reais antes de mover ou renomear páginas.

## Entidades de domínio conhecidas

- Identidade e acesso: `User`, `Role`, `Membership`.
- Organizações: `Organization`.
- Academia: `Course`, `CourseVersion`, `Module`, `Lesson`, `Certification`.
- Rede territorial: `Location`, `Professional`.
- Operações: `Mission`.

## Decisões que precisam ser confirmadas com o responsável pelo produto

- Se clientes são apenas empresas/instituições ou também pessoas físicas.
- Quais papéis existem e que ações cada um pode executar.
- Quem pode criar, revisar e aprovar locais, missões, cursos e certificações.
- Se um usuário pode pertencer a várias organizações e como troca de contexto.
- Regras de contratação, cobrança e visibilidade de relatórios.
- Requisitos de retenção, consentimento e acesso a documentos pessoais.

Não invente respostas para essas questões. Proponha defaults seguros e solicite confirmação quando afetarem o modelo de dados ou o fluxo principal.
