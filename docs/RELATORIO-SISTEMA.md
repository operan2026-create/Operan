# OPERAN — Relatório técnico completo do sistema

> Data do levantamento: 26/10/2026
> Escopo: repositório `C:\Users\vhugo\Documents\OPERAN` (backend, frontend, banco, infra e testes)
> Método: leitura estática do código, execução da suíte de testes, checagem de migrations no PostgreSQL local e build de produção do frontend.

---

## 1. Sumário executivo

O OPERAN está em **estágio avançado de desenvolvimento**, com a espinha dorsal funcional e uma suíte de testes verde, mas **ainda não pronto para produção**. O sistema já possui:

- Três áreas lógicas com layouts e guards distintos: **Administração** (`/admin`), **Cliente** (`/cliente`) e **Participante** (`/participante`).
- Conta global de participante com **jornadas independentes** (`LOCATIONS` e `PROFESSIONALS`).
- Fluxo completo de **convites individuais e links públicos reutilizáveis**, com rascunho de cadastro criptografado e retomável.
- Camada de **dados sensíveis criptografada em repouso** (AES-256-GCM) e índices cegos determinísticos (**HMAC-SHA256**) para busca.
- **RBAC** e isolamento multi-tenant aplicados no backend, com testes cobrindo IDOR e vazamento entre organizações.
- **Login com rate limiting/lockout** por conta e por IP, com backend Redis opcional e fallback em memória.
- **Missões** com máquina de estados, candidaturas, convites diretos e decisão por gestor.
- **Academia** com cursos, versões, módulos, aulas, conclusão de aulas e certificação condicionada a 100% de conclusão.
- **Rede territorial** (locais, profissionais), **workflow de representantes** em 4 etapas e **documentos** com validação por magic bytes.

**Números atuais:**

| Indicador | Valor |
|---|---|
| Arquivos Python no backend | 63 (~9.800 linhas) |
| Tabelas/modelos SQLAlchemy | 31 |
| Endpoints HTTP | 102 |
| Migrations Alembic | 10 (head `b8d2f4a6c9e1`, aplicado no banco local) |
| Arquivos TS/TSX no frontend | 43 (~7.391 linhas) |
| Páginas React | 20 |
| Testes backend | 74 (74 passando com PostgreSQL/Redis de teste; 4 pulados por padrão) |
| Build de produção frontend | OK (aviso de chunk > 500 kB) |
| Commits no repositório | 2 (`initial commit`, `4349de5`) |
| Alterações não commitadas | 50 arquivos modificados + 52 novos (antes e durante as correções P0) |

**Principais lacunas:** telas parcialmente conectadas (missões, workflow de locais, avatar, criação de organizadora), ausência de estados de erro em várias consultas, autenticação sem contexto global no frontend (chamadas duplicadas a `/auth/me`), ausência de revogação/refresh de JWT, MFA apenas reservado (não implementado) e dependências Python sem versionamento.

---

## 2. Stack tecnológico

### Backend

| Item | Versão / escolha |
|---|---|
| Linguagem | Python 3.11.0 |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x assíncrono + asyncpg |
| Banco | PostgreSQL 15 (Docker) |
| Migrations | Alembic |
| Validação | Pydantic v2 + pydantic-settings |
| Hash de senha | Argon2 (argon2-cffi / passlib) |
| JWT | PyJWT, HS256/384/512, expiração padrão de 30 min |
| Criptografia de campos | AES-256-GCM (`cryptography`) |
| Uploads | python-multipart |
| Testes | pytest + pytest-asyncio + httpx + aiosqlite |

### Frontend

| Item | Versão |
|---|---|
| React | 19.2.x |
| React Router DOM | 7.18.x (API declarativa estilo v6) |
| Vite | 8.2.x |
| TypeScript | 6.0.x (`strict: true`) |
| Tailwind CSS | 4.3.x (plugin Vite, sem config JS) |
| TanStack React Query | 5.102.x |
| Axios | 1.20.x |
| Ícones | lucide-react |
| Node / npm | 22.17.1 / 10.9.2 |

### Infra

- Docker Compose com **PostgreSQL 15** (host `5433` → container `5432`) e **Redis 7** (host `6379`).
- O backend **não** é um serviço do `docker-compose.yml`; roda fora do contêiner (venv local).
- O frontend também roda fora do contêiner (Vite dev server).
- Existe um segundo contêiner `operan_db_55432` em execução local, não descrito no compose.

---

## 3. Arquitetura e estrutura

### 3.1 Backend (`backend/`)

```
backend/
├── app/
│   ├── main.py                # criação da app, CORS, /health, include do router
│   ├── api/v1/                # 15 módulos de rotas (102 endpoints)
│   ├── core/                  # config, database, deps (RBAC/tenant)
│   ├── models/                # 9 arquivos, 31 tabelas
│   ├── schemas/               # contratos Pydantic
│   ├── security/              # jwt, encryption, encrypted_types, hashing
│   └── services/              # 15 serviços de regra de negócio
├── alembic/versions/          # 9 migrations, cadeia linear
├── tests/                     # 4 arquivos, 44 testes
├── create_admin.py            # bootstrap de administrador
├── requirements.txt           # sem versões pinadas
└── requirements-dev.txt
```

Inicialização: `app/main.py`

- `FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)`.
- OpenAPI em `/api/v1/openapi.json`.
- CORS habilitado a partir de `BACKEND_CORS_ORIGINS` (padrão `http://localhost:5173`, `http://localhost:3000`), com credenciais.
- Healthcheck público: `GET /health` → `{"status":"ok","project":"OPERAN API"}`.
- **Não cria tabelas nem faz seed no startup** — schema é responsabilidade exclusiva do Alembic.

### 3.2 Frontend (`frontend/src/`)

```
frontend/src/
├── App.tsx                    # rotas + QueryClientProvider
├── api/client.ts              # axios com baseURL fixa e interceptors
├── components/                # UI, Sidebar, ProtectedRoute, modal de workflow
├── hooks/                     # useAuth, useArea
├── layouts/                   # AdminLayout, ClientLayout, ParticipantLayout
├── lib/                       # queryClient, authRoutes, errors, download, funções
├── pages/                     # 20 páginas
└── types/index.ts             # tipos manuais (525 linhas)
```

- `baseURL` fixa em `http://localhost:8000/api/v1` (hardcoded, sem variável de ambiente nem proxy Vite).
- Token JWT armazenado em `localStorage` (`operan_token`).
- Interceptor 401 limpa token/cache e redireciona para `/login`.
- Sem `AuthContext`: cada `useAuth()` mantém estado próprio e pode disparar `/auth/me` (16 pontos de uso).

---

## 4. Modelo de dados (31 tabelas)

### 4.1 Identidade e organização

| Tabela | Destaques |
|---|---|
| `users` | `public_id` único, `email_hash` único (blind index HMAC-SHA256) + `email_encrypted`, Argon2, status `ACTIVE/PENDING/BLOCKED`, `mfa_enabled`, `mfa_secret` reservado (não usado; ver `docs/MFA-LIMITACAO.md`) |
| `organizations` | `public_id`, `cnpj_hash` único + `cnpj_encrypted`, status `ACTIVE/INACTIVE/SUSPENDED` |
| `roles` | `name` único, `is_system` (protege papéis de sistema) |
| `memberships` | vínculo usuário↔organização↔papel; único por `(user_id, organization_id)`; status `ACTIVE/INVITED/SUSPENDED` |

Papéis padrão criados por `user_service.ensure_default_roles`: `ADMIN` (system), `CLIENT_ADMIN`, `CLIENT_OPERATOR`, `PARTICIPANT`.

### 4.2 Rede territorial

| Tabela | Destaques |
|---|---|
| `locations` | vínculo opcional com organização (`SET NULL`), cidade/UF indexados, capacidade, acessibilidade, `status` `DECLARADO/VISTORIADO/CONFIRMADO`, `reliability_score` |
| `professionals` | 1:1 com `users`, nome/CPF/telefone/cidade/UF criptografados, `cpf_hash` único, disponibilidade, reputação |

### 4.3 Missões

| Tabela | Destaques |
|---|---|
| `missions` | tipo, status, organização, local, `assigned_user_id`, cidade/UF, recompensa, prazo, `checklist` JSON, `required_function` |
| `mission_applications` | único por `(mission_id, user_id)`, status `APPLIED/WITHDRAWN/SELECTED/REJECTED` |
| `mission_invitations` | único por `(mission_id, user_id)`, status `INVITED/ACCEPTED/DECLINED/CANCELLED` |

Máquina de estados em `mission_service.MISSION_TRANSITIONS`:

```
OPEN        → ASSIGNED | CANCELLED
ASSIGNED    → IN_PROGRESS | CANCELLED
IN_PROGRESS → COMPLETED | CANCELLED
COMPLETED / CANCELLED → (terminal)
```

### 4.4 Academia

| Tabela | Destaques |
|---|---|
| `courses` | organização opcional, status `DRAFT/PUBLISHED/ARCHIVED`, audiência `GLOBAL/LOCATIONS/PROFESSIONALS` |
| `course_versions` | versão, `is_active`, `content_hash`, módulos ordenados |
| `modules` / `lessons` | ordenação explícita; tipo de aula `VIDEO/PDF/TEXT` |
| `lesson_completions` | único por `(user_id, lesson_id)` |
| `certifications` | status `VALID/EXPIRED/REVOKED`, nota opcional, emissão/expiração |

### 4.5 Conta global e cadastro de participantes (18 tabelas)

| Tabela | Destaques |
|---|---|
| `person_profiles` | 1:1 com usuário; PII criptografada (nome, CPF, RG, telefone, endereço, nascimento, gênero, bio), avatar criptografado, `cadastral_status` |
| `participant_bank_accounts` | dados bancários/PIX criptografados, `account_fingerprint` único por usuário, status de verificação |
| `participant_family_members` | nome/telefone/CPF criptografados, parentesco (coluna `relationship`), responsável legal |
| `participant_client_links` | vínculo participante↔organização; único por `(user_id, organization_id)`; origem em convite/missão |
| `participant_validation_events` | trilha de validação cadastral por escopo, revisor e organização |
| `registration_drafts` | rascunho criptografado, `token_hash`, passo atual, expiração, status |
| `journey_enrollments` | jornadas `LOCATIONS`/`PROFESSIONALS`, status, ativação, único por `(user_id, journey_type)` |
| `invitations` | convite individual; token hasheado/criptografado, propósito, missão, local, categorias de dados exigidas, status e expiração |
| `public_invitations` | link público reutilizável; `max_uses`, `uses_count`, status `ACTIVE/REVOKED/EXPIRED` |
| `representative_school_links` | vínculo representante↔local; único por `(representative_user_id, location_id)` |
| `location_workflow_events` | etapas `CAPTURE/DOCUMENTATION/INSPECTION/RELEASE`, status do workflow |
| `documents` | dono polimórfico (`PERSON/LOCATION/REPRESENTATIVE_LINK`), `storage_key` único, MIME/tamanho/SHA-256, status de revisão |
| `qualification_requirements` | requisito curso↔função, validade, único por `(course_version_id, function_name)` |
| `professional_qualifications` | função habilitada por usuário, origem em certificação, status/validade, único por `(user_id, function_name)` |
| `participant_consents` | consentimento por tipo/categoria, versão de política, base legal, IP/user-agent |
| `audit_logs` | ator, ação, entidade, organização, detalhes JSON, IP/user-agent |

Enums relevantes: `JourneyType`, `JourneyStatus`, `InvitationPurpose`, `ParticipantDataCategory`, `ParticipantValidationStatus/Scope`, `ApplicationStatus`, `MissionInvitationStatus`, `WorkflowStage/Status`, `DocumentStatus`, `QualificationStatus`.

---

## 5. API — 102 endpoints

Todos sob `/api/v1`. Legenda de autenticação: **Público**, **Contexto** (`get_current_user_context` + usuário `ACTIVE`), **Admin**, **Profissional**, **Representante**, **Opcional**.

### 5.1 Sistema e autenticação (5)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/health` | Público | Healthcheck |
| POST | `/auth/register` | Público | Auto-registro; cria `PENDING` com papel `PARTICIPANT` |
| POST | `/auth/register-collaborator` | Público | Desativado; retorna `410 Gone` |
| POST | `/auth/login` | Público | Login; rejeita usuário não `ACTIVE` (403) |
| GET | `/auth/me` | Contexto | Usuário atual com papéis, memberships, jornadas e qualificações |

### 5.2 Usuários e organizações (7)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/users` | Admin | Lista usuários paginada, filtro por status |
| PATCH | `/users/{id}/status` | Admin | Altera status; impede auto-bloqueio e remoção do último admin |
| POST | `/organizations` | Admin | Cria organização (CNPJ opcional) |
| GET | `/organizations/my` | Contexto | Organização cliente principal do usuário |
| GET | `/organizations` | Contexto | Admin vê todas; cliente vê apenas as suas |
| GET | `/organizations/{id}` | Contexto | Escopo por organização; 403 fora do escopo |
| PATCH | `/organizations/{id}/status` | Admin | Altera status |

### 5.3 Papéis (2)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/roles` | Admin | Cria papel; `is_system` forçado a `false` |
| GET | `/roles` | Admin | Lista papéis |

### 5.4 Academia (9)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/academy/courses` | Contexto | Catálogo conforme escopo/audiência/publicação |
| POST | `/academy/courses` | Contexto | Admin ou `CLIENT_ADMIN`; curso de cliente forçado à própria org |
| GET | `/academy/courses/{id}` | Contexto | Detalhe com escopo |
| POST | `/academy/versions/{id}/modules` | Admin | Cria módulo |
| POST | `/academy/modules/{id}/lessons` | Admin | Cria aula |
| POST | `/academy/lessons/{id}/complete` | Contexto | Marca aula concluída (curso publicado) |
| POST | `/academy/versions/{id}/certify` | Contexto | Emite certificação somente com 100% de conclusão |
| GET | `/academy/my-certifications` | Contexto | Certificações do próprio usuário |
| POST | `/academy/seed` | Admin | Popula cursos padrão |

### 5.5 Locais (4)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/locations` | Contexto | Admin tudo; cliente própria org; participante rede validada |
| POST | `/locations` | Contexto | Admin ou `CLIENT_ADMIN`; cliente forçado a `DECLARADO` |
| PATCH | `/locations/{id}/status` | Contexto | Transição validada; admin ou gestor da org |
| POST | `/locations/seed` | Admin | Popula locais padrão |

### 5.6 Profissionais (2)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/professionals` | Contexto | Admin tudo; cliente apenas vinculados; filtros cidade/UF/função |
| POST | `/professionals` | Admin | Cria perfil profissional |

### 5.7 Missões (14)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/missions` | Contexto | Escopo por papel; filtros status/cidade/UF |
| POST | `/missions` | Contexto | Admin ou `CLIENT_ADMIN`; valida local e escopo |
| POST | `/missions/{id}/applications` | Profissional | Candidatura |
| GET | `/missions/applications/me` | Contexto | Minhas candidaturas |
| POST | `/missions/{id}/invitations` | Contexto | Convida profissionais (valida gestão) |
| GET | `/missions/{id}/invitations` | Contexto | Lista convites da missão |
| GET | `/missions/invitations/me` | Profissional | Meus convites |
| POST | `/missions/invitations/{id}/accept` | Profissional | Aceita convite |
| POST | `/missions/invitations/{id}/decline` | Profissional | Recusa convite |
| GET | `/missions/{id}/applications` | Contexto | Lista candidaturas (gestor/admin) |
| PATCH | `/missions/applications/{id}/decision` | Contexto | Seleciona/rejeita candidatura |
| DELETE | `/missions/applications/{id}` | Contexto | Retira a própria candidatura |
| PATCH | `/missions/{id}/status` | Contexto | Transição pela máquina de estados |
| POST | `/missions/seed` | Admin | Popula missões padrão |

### 5.8 Conta global (18)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/account/me` | Visão completa da conta |
| GET/PATCH | `/account/profile` | Lê/atualiza perfil global (auditado) |
| GET/POST | `/account/avatar` | Baixa/atualiza avatar |
| GET/POST | `/account/bank-accounts` | Lista/cria contas bancárias |
| PATCH/DELETE | `/account/bank-accounts/{id}` | Atualiza/remove com checagem de dono |
| GET/POST | `/account/family-members` | Lista/cria familiares |
| PATCH/DELETE | `/account/family-members/{id}` | Atualiza/remove com checagem de dono |
| GET | `/account/journeys` | Lista jornadas |
| PATCH | `/account/users/{user_id}/journeys/{type}` | Admin altera jornada de terceiro |
| GET/POST | `/account/consents` | Lista/registra consentimento |
| PATCH | `/account/consents/{id}/revoke` | Revoga consentimento |

### 5.9 Convites (15)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/invitations` | Contexto | Admin/cliente cria convite individual; retorna token único |
| GET | `/invitations` | Contexto | Lista conforme escopo |
| POST | `/invitations/{id}/revoke` | Contexto | Revoga |
| POST | `/invitations/{id}/regenerate` | Contexto | Regenera token |
| POST | `/invitations/public` | Contexto | Cria link público reutilizável |
| GET | `/invitations/public` | Contexto | Lista links públicos |
| POST | `/invitations/public/{id}/revoke` | Contexto | Revoga link público |
| GET | `/invitations/public/validate/{token}` | Opcional | Valida link público |
| POST | `/invitations/public/{token}/accept` | Opcional | Aceita link (pode criar conta); retorna JWT |
| GET/PUT | `/invitations/public/{token}/draft` | Público | Lê/salva rascunho |
| GET/PUT | `/invitations/{token}/draft` | Público | Rascunho de convite individual |
| GET | `/invitations/validate/{token}` | Público | Valida convite individual |
| POST | `/invitations/{token}/accept` | Opcional | Aceita convite individual; retorna JWT |

### 5.10 Representantes (11)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/representatives/schools` | Representante | Escolas vinculadas |
| GET | `/representatives/schools/{id}` | Representante | Detalhe: vínculo, eventos e documentos |
| POST/GET | `/representatives/schools/{id}/documents` | Representante | Envia/lista documentos do local |
| GET | `/representatives/schools/{id}/events` | Contexto | Eventos de workflow |
| POST | `/representatives/schools/{id}/submit/{stage}` | Representante | Envia etapa |
| POST | `/representatives/schools/{id}/request/{stage}` | Representante | Alias de envio de etapa |
| GET | `/representatives/locations/{id}/links` | Contexto | Lista representantes do local |
| PATCH | `/representatives/links/{id}` | Contexto | Atualiza vínculo |
| POST | `/representatives/locations/{id}/stages/{stage}/decision` | Contexto | Aprova/recusa etapa |
| POST | `/representatives/locations/{id}/stages/{stage}/submit` | Contexto | Envia etapa em nome do staff |

### 5.11 Documentos, qualificações, auditoria e participantes (16)

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/documents/me` | Contexto | Meus documentos |
| POST | `/documents/me` | Contexto | Upload multipart do próprio documento |
| GET | `/documents/{id}/download` | Contexto | Download com checagem de dono/representante/admin |
| PATCH | `/documents/{id}/review` | Admin | Aprova/rejeita documento |
| DELETE | `/documents/{id}` | Contexto | Admin ou uploader |
| GET | `/qualifications/requirements` | Contexto | Lista requisitos |
| POST | `/qualifications/requirements` | Admin | Cria requisito |
| GET | `/qualifications/me` | Profissional | Minhas qualificações |
| POST | `/qualifications/{user_id}` | Admin | Emite qualificação |
| GET | `/qualifications/{user_id}` | Admin | Lista qualificações do usuário |
| GET | `/audit` | Admin | Lista logs de auditoria com filtros |
| GET | `/participants` | Contexto | Diretório escopado (admin/cliente) |
| GET | `/participants/{id}` | Contexto | Detalhe com PII mascarada |
| GET | `/participants/{id}/avatar` | Contexto | Avatar do participante |
| GET | `/participants/{id}/validations` | Admin | Histórico de validação |
| POST | `/participants/{id}/validations` | Admin | Registra validação |

---

## 6. Serviços e regras de negócio

| Serviço | Responsabilidade |
|---|---|
| `user_service` | Hash de e-mail, criação/autenticação de usuário, papéis padrão, organização admin |
| `organization_service` | Criação/status de organização, hash de CNPJ, escopo |
| `network_service` | Locais, profissionais, qualificações, seed inicial |
| `mission_service` | CRUD, máquina de estados, candidaturas, decisões, convites diretos, seed |
| `invitation_service` | Criação/validação/aceite/revogação de convites e links públicos; criação de usuário/profissional |
| `registration_draft_service` | Rascunho criptografado e retomável por token |
| `account_service` | Perfil, avatar, banco, família, jornadas, vínculos e composição da conta |
| `qualification_service` | Requisitos, validação de certificação e emissão de qualificações |
| `representative_service` | Vínculos representante↔escola, eventos e decisões de workflow |
| `document_service` | Upload, listagem, download, revisão e exclusão de documentos |
| `participant_directory_service` | Diretório escopado por vínculo ativo e eventos de validação |
| `academy_service` | Cursos/versões/módulos/aulas, conclusão e elegibilidade a certificação |
| `audit_service` | Registro de auditoria com redação de valores e metadados de request |
| `storage_service` | Armazenamento local privado com proteção contra path traversal |
| `participant_service` | Shim de compatibilidade (não usar) |

**Regras relevantes verificadas:**

- Certificação exige versão publicada/ativa, ao menos uma aula e 100% das aulas concluídas.
- Consulta de locais do participante só expõe rede pública/validada.
- Missões: cliente só opera `ASSIGNED`/`CANCELLED`; participante só `IN_PROGRESS`/`COMPLETED` na própria missão.
- Diretório de participantes do cliente usa `ParticipantClientLink` ativo.
- Documentos validados por magic bytes e servidos apenas por endpoint autenticado (sem static).
- Aceite de link público usa `SELECT ... FOR UPDATE` para evitar corrida em `max_uses`.

---

## 7. Segurança

### 7.1 Controles positivos confirmados

- Senhas com **Argon2**.
- JWT verificado quanto a assinatura/expiração; algoritmo restrito a HS256/384/512.
- `SECRET_KEY`, `CRYPTO_KEY` e `PII_INDEX_KEY` validados no startup (tamanho, base64 quando aplicável, rejeição de placeholders fracos).
- **AES-256-GCM** com nonce aleatório de 12 bytes por operação.
- PII de participante criptografada em repouso; respostas do diretório mascaram CPF/telefone.
- Índices de busca de PII com **HMAC-SHA256 chaveado** (blind index), não SHA-256 puro.
- Login com **rate limiting/lockout** por conta e IP, auditoria de bloqueio e resposta genérica.
- Autorização por `UserContext` derivada de memberships ativas e jornadas; escopo por organização aplicado em consultas.
- Testes cobrem IDOR entre organizações, escalada de papel, admin não controlável por registro público e isolamento de missões.
- `.env` ignorado/untracked; `.dockerignore` exclui `.env` e storage.
- Proteção contra path traversal no armazenamento.
- CORS restrito a origens explícitas.

### 7.2 Achados — Alta severidade

1. ✅ **Corrigido.** **Aceite de convite reativava contas suspensas/bloqueadas.**
   `app/services/invitation_service.py`: o aceite só promove `PENDING → ACTIVE`; `BLOCKED` recebe 403 genérico.
2. ✅ **Corrigido.** **Sem rate limiting / lockout de login.**
   `app/api/v1/auth.py` + `app/services/login_limiter.py`: limite por conta/IP, bloqueio exponencial, Redis opcional e verificação dummy de Argon2.
3. ⚠️ **Mitigado/documentado.** **MFA não implementado e segredo em texto puro.**
   `mfa_secret` é reservado, nunca escrito, e a UI não promete MFA; ativação completa continua pendente (`docs/MFA-LIMITACAO.md`).
4. ✅ **Corrigido.** **Hashes determinísticos sem sal/HMAC para PII.**
   E-mail, CPF, RG e CNPJ usam blind index HMAC-SHA256 com `PII_INDEX_KEY`; migração `b8d2f4a6c9e1` recalculou os dados.

### 7.3 Achados — Média severidade

5. **Falhas de descriptografia silenciadas.** `security/encryption.py:51-52` retorna `"[Encrypted Data]"` em qualquer exceção, mascarando erro de rotação de chave ou adulteração (comportamento intencional e testado).
6. ✅ **Corrigido.** **Corrida em atribuição de missão.** `missions.assigned_user_id` continua sem índice único, mas decisões/aceites usam `SELECT ... FOR UPDATE` e revalidam o estado após o lock; suíte PostgreSQL cobre os cenários concorrentes.
7. **Sem revogação/refresh de JWT.** Logout, troca de senha, suspensão e mudança de papel não invalidam tokens ativos até expirarem.
8. **Contêiner roda como root**, sem multi-stage e sem healthcheck (`backend/Dockerfile`).
9. **Compose expõe Postgres/Redis no host**, com credencial literal e Redis sem autenticação; Redis agora é usado pelo rate limiting, aumentando a importância de autenticá-lo.
10. ✅ **Corrigido.** **Bootstrap de admin via argv.** `create_admin.py` usa env/prompt, não redefine senha existente, não reativa bloqueado por padrão e registra auditoria.

### 7.4 Achados — Baixa / endurecimento

11. `DATABASE_URL` tem credencial de desenvolvimento como default.
12. `allow_methods`/`allow_headers` são `*` no CORS (origens são explícitas).
13. `requirements.txt` sem versões pinadas; dependências de teste fora do `requirements.txt`.
14. Armazenamento local em disco impede escala horizontal sem storage compartilhado.
15. Dependência de os chamadores registrarem eventos de auditoria corretamente.

---

## 8. Frontend — rotas e maturidade

### 8.1 Rotas

**Públicas**

| Rota | Página |
|---|---|
| `/login` | `LoginPage` |
| `/cadastro-colaborador` | Redireciona para `/login` (fluxo desativado) |
| `/convite/:token` | `InvitationAcceptPage` (convite individual) |
| `/convite-publico/:token` | `InvitationAcceptPage` (link público) |
| `/sem-acesso` | `NoAccessPage` |
| `/` e `*` | Redirecionam para `/login` |

**Administração** (`ProtectedRoute` `ADMIN`, `AdminLayout`)

`/admin` · `/admin/organizations` · `/admin/academy` · `/admin/academy/course/:courseId/lesson/:lessonId` · `/admin/locations` · `/admin/missions` · `/admin/network` · `/admin/invitations` · `/admin/participants`

**Cliente** (`ADMIN` ou `CLIENT`, `ClientLayout`)

`/cliente` · `/cliente/locations` · `/cliente/missions` · `/cliente/network` · `/cliente/invitations` · `/cliente/participants`

**Participante** (`ADMIN` ou `PARTICIPANT`, `ParticipantLayout`)

`/participante` · `/participante/academy` · `/participante/academy/course/:courseId/lesson/:lessonId` · `/participante/missions` · `/participante/escolas` · `/participante/conta`

### 8.2 Maturidade das páginas

| Página | Maturidade | Observações |
|---|---|---|
| `LoginPage` | Completa | Erro local pode ser perdido pelo redirect global de 401 |
| `NoAccessPage` | Completa | — |
| `InvitationAcceptPage` | Completa | 4 etapas, rascunho, compressão de imagem, consentimento, estados robustos |
| `ParticipantsPage` | Completa | Lista, detalhe, validação admin |
| `InvitationsPage` | Completa | Convites individuais e links públicos completos |
| `RepresentativeSchoolsPage` | Completa | Workflow em 4 etapas e documentos |
| `AccountPage` | Parcial | Perfil/banco/família/documentos OK; avatar não conectado à UI |
| `ParticipantMissionsPage` | Funcional | Sem feedback de erro nas mutações |
| `NetworkPage` | Completa (consulta) | Sem erro explícito de query |
| `LessonPlayerPage` | Parcial | Sem tratamento de curso inexistente/sem aulas |
| `OperationalPassportPage` | Parcial | Funções habilitadas hardcoded |
| `StudentAcademyPage` | Parcial | Sem estado vazio/erro; curso sem aula não trata clique |
| `AcademyAdminPage` | Parcial | Só cria curso; sem módulos/aulas/versões/publicação |
| `AcademyHubPage` | Parcial | Hub OK; bloco de convite é stub (`copied` nunca muda) |
| `LocationsPage` | Parcial | Workflow de representantes inacessível (`workflowLocation` nunca definido) |
| `MissionsPage` | Incompleta | UI de candidaturas e convites existe como código órfão |
| `ClientDashboardPage` | Parcial | Sem loading/erro; `/professionals` consultado e não exibido |
| `DashboardPage` | Parcial | Contagens reais; status de serviços hardcoded |
| `OrganizationsPage` | Parcial | Botão “Nova Organizadora” sem ação |
| `CollaboratorRegisterPage` | Morta | Não roteada; backend retorna 410 |

### 8.3 Problemas transversais do frontend

- `useAuth` sem `AuthContext`: estado duplicado e múltiplas chamadas a `/auth/me`.
- `baseURL` hardcoded; sem `.env`/`VITE_*`/proxy.
- Interceptor 401 também atua no próprio login (pode apagar mensagem de erro).
- Cache React Query fragmentado: dashboards usam `['locations']`/`['missions']`, telas usam `['locations', area]`/`['missions', area]`.
- Estados de erro ausentes em boa parte das queries; vários `.catch(() => [])` mascaram falha como vazio.
- Links do menu para `/admin/security` e `/admin/settings` não existem e caem no fallback `*` (redireciona para `/login`).
- Tipos manuais com pequenas divergências (`User.professional`, `Invitation.token`, `Mission.checklist`, `Location.reliability_score`).
- Sem ESLint/Prettier e sem testes de frontend.
- `index.html` com `lang="en"` e título “OPERAN Admin” para todas as áreas.
- Build gera chunk único de ~508 kB (aviso de code splitting).

---

## 9. Banco de dados e migrations

Cadeia linear aplicada, head única:

```
d2d45949caaa  Initial schema (organizations, users, roles, memberships)
4df8602a535e  Academy models
4bf3169488a5  Locations, Professionals, Missions
9f1c2b3d4e5f  Lesson completions
c7a1e4d2b9f0  Global account, journeys, invitations, governance
b2e4f6a8c1d3  Invitation links, mission invitations
d4f7a9c2e6b8  Public invitation links (reusable)
e6a2b8c4d913  Encrypt participant PII and avatar (data migration)
f1b3c5d7e9a2  Participant global registration
b8d2f4a6c9e1  Blind index PII HMAC (data migration, HEAD)
```

- `alembic current` no PostgreSQL local: **`b8d2f4a6c9e1 (head)`**.
- `alembic/env.py` sobrescreve a URL com `settings.DATABASE_URL`; o placeholder do `alembic.ini` não é usado.
- `e6a2b8c4d913` e `b8d2f4a6c9e1` são migrações de dados; downgrade exige `CRYPTO_KEY` e cuidado.
- `b8d2f4a6c9e1` recifra os índices de e-mail, CPF, RG e CNPJ com HMAC e exige `PII_INDEX_KEY`. Hashes de campos sem uso em consulta (RG/CNPJ) são limpos quando o ciphertext não pode ser decifrado, com aviso.
- `env.py` não configura `compare_type` nem naming convention; autogenerate pode não detectar mudanças de tipo e nomes de constraint dependem dos modelos.
- Teste garante head única incluindo a migration de blind index.

---

## 10. Testes

### 10.1 Execução atual

```
74 passed, 4 warnings in ~33s   # com OPERAN_TEST_POSTGRES_URL e OPERAN_TEST_REDIS_URL
70 passed, 4 skipped            # padrão (SQLite + limitador em memória)
```

Verificações: suíte completa (`pytest -q`), testes PostgreSQL de concorrência (`OPERAN_TEST_POSTGRES_URL`), teste do backend Redis (`OPERAN_TEST_REDIS_URL`) e build do frontend (`npm run build`).

### 10.2 Cobertura por arquivo

**`test_api_security.py` (13)** — anônimo em rotas privadas; login válido/inválido/pendente; registro público não vira admin; participante não cria missão; cliente não acessa outra org; isolamento/transições de missão; locais e aprovação admin; IDOR de organização; certificação exige conclusão total; cursos escopados; não certificar curso draft; `is_system` não controlável; settings inseguros rejeitados.

**`test_global_account.py` (12)** — conta única com jornadas independentes; workflow de representante e liberação; qualificação exige certificação e jornada ativa; candidatura/seleção escopadas; convite de local exige escola vinculada; convite direto de missão e filtro de rede; link público reutilizável até `max_uses`; revogação e aceite por usuário logado; novo participante quando e-mail difere; link público de local cria vínculo; convite exige foto; PII/documentos criptografados.

**`test_participant_registration_data.py` (12)** — PII de banco/família criptografada; rascunho criptografado; propósito/missão persistidos; vínculo único por usuário/org; mascaramento e posse em banco/família; aceite cria vínculo ativo; diretório escopado por vínculo; validação admin atualiza status; convite de missão carrega finalidade/dados; rascunho retomável; head única do Alembic.

**`test_security_rbac.py` (7)** — Argon2; AES-GCM nonce aleatório e fallback em adulteração; JWT `sub`/`role`; JWT expirado; contexto admin; escopo cliente por organização; contexto participante via `Professional`.

**`test_security_p0.py` (27)** — reativação por convite restrita a `PENDING`; bloqueio de conta `BLOCKED`; bootstrap de admin sem senha em argv e sem reativar bloqueado; rate limiting por conta/IP, expiração, reset em sucesso, resposta genérica e fallback fail-open/fail-closed; roundtrip Redis opcional; indisponibilidade de Redis com timeout limitado; separação obrigatória de `PII_INDEX_KEY`; ausência de promessa de MFA; blind index HMAC normalizado e migração de dados.

**`test_postgres_concurrency.py` (3, opcional)** — decisões concorrentes de candidatura, dupla decisão da mesma candidatura e aceites concorrentes de convite com `SELECT ... FOR UPDATE` em PostgreSQL real.

### 10.3 Limitações da suíte

- Integração padrão roda em **SQLite em memória**; os fluxos de lock e atribuição de missão têm suíte dedicada opcional em **PostgreSQL real** (`test_postgres_concurrency.py`).
- Rate limiting tem suíte com backend em memória e teste opcional contra Redis real (`OPERAN_TEST_REDIS_URL`).
- Sem testes de frontend (unitário/E2E).
- Sem testes de carga.

---

## 11. Infraestrutura e operação

### 11.1 Serviços locais verificados

| Serviço | Situação |
|---|---|
| PostgreSQL (`operan_db`) | Up, healthy, host `5433`; banco usado pelos testes PG em `55432` |
| Redis (`operan_redis`) | Up, healthy, host `6379` (integrado ao rate limiting; fallback em memória) |
| Segunda instância (`operan_db_55432`) | Up, host `55432` (fora do compose) |
| Backend FastAPI | Rodando em `127.0.0.1:8000`, `/health` 200 |
| Frontend Vite | Rodando (dev) |

### 11.2 Comandos úteis

```powershell
# Backend
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Migrations
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic current

# Testes
.\venv\Scripts\python.exe -m pytest -q

# Frontend
cd frontend
npm run dev
npm run build

# Infra
docker compose up -d
```

### 11.3 Configuração

- `.env` do backend contém `DATABASE_URL`, `SECRET_KEY`, `CRYPTO_KEY`, `PII_INDEX_KEY` e parâmetros opcionais de rate limiting/Redis.
- `.env.example` documenta os campos e alerta que trocar `CRYPTO_KEY` torna ilegível o ciphertext existente; trocar `PII_INDEX_KEY` invalida os blind indexes e exige recálculo.
- **Deploy:** definir `PII_INDEX_KEY` (≥32 caracteres, gerada aleatoriamente, fora do banco) e rodar `alembic upgrade head` antes de subir o backend. Sem a chave o app não inicia; sem a migration os logins falham.
- Rate limiting: Redis via `REDIS_URL`; sem Redis usa memória por processo (`LOGIN_RATE_LIMIT_FAIL_OPEN` controla indisponibilidade).
- Limites: documentos 10 MB, avatar 5 MB; storage em `storage/participant-documents`.
- CORS padrão: `http://localhost:5173`, `http://localhost:3000`.
- `create_admin.py` exige `OPERAN_ADMIN_PASSWORD` (ou prompt), não redefine senha existente, não reativa `BLOCKED` sem `--activate-existing` e registra auditoria.

---

## 12. Estado do repositório

- Branch `main`, 2 commits:
  - `4349de5` — auditoria técnica, RBAC em rotas/serviços, layouts Cliente/Participante e documentação.
  - `1533574` — initial commit.
- **50 arquivos rastreados modificados** e **52 arquivos novos não rastreados**, cobrindo participantes, convites, documentos, qualificações, representantes, conta global, correções P0 e testes.
- Nenhuma alteração commitada desde o trabalho recente de conta global/convites.
- O teste mais recente modificado foi `test_global_account.py`; a suíte está verde.

---

## 13. Riscos e pendências priorizadas

### P0 — Segurança e integridade (corrigidos na Fase 1)

1. ✅ Reativação por convite restrita a usuários `PENDING`; `BLOCKED` recebe 403 genérico sem reativação.
2. ✅ Rate limiting/lockout por conta e IP no login, com Redis opcional, fallback em memória, resposta genérica e verificação dummy de Argon2 para e-mail inexistente.
3. ✅ Hashes determinísticos de PII substituídos por **blind index HMAC-SHA256** (`PII_INDEX_KEY`), com migração de dados `b8d2f4a6c9e1`.
4. ✅ `mfa_secret` documentado como reservado e não prometido na UI; ativação completa de MFA permanece pendência de escopo (ver `docs/MFA-LIMITACAO.md`).
5. ✅ Locking (`SELECT ... FOR UPDATE`) e revalidação em decisão de candidatura e aceite de convite, incluindo nova leitura travada da própria candidatura contra decisões duplicadas, com testes PostgreSQL de concorrência.
6. ✅ Bootstrap de admin com senha via env/prompt, sem redefinir senha existente, sem reativar `BLOCKED` por padrão e com auditoria.

Todos os itens acima têm testes de regressão. A suíte completa está verde e o build do frontend passa.

### Fase 1.1 — auditoria das correções P0

- Chaves separadas: a aplicação recusa iniciar se `PII_INDEX_KEY` for igual a `SECRET_KEY` ou `CRYPTO_KEY`.
- Rate limiting com timeouts de 1 s no Redis para não travar login quando o cache está indisponível; política fail-open/fail-closed coberta por teste.
- Procedimentos de rotação de chaves, operação com Redis multi-worker e recuperação do CNPJ documentados em `docs/OPERACAO-SEGURANCA.md`.
- **Incidente de CNPJ:** um único registro (`organizations.id` `1dc879b5-0067-4f20-8d59-7b61c2ad9c6a`) tem ciphertext válido em formato, mas não decifra com a chave atual nem com a padrão histórica. O valor original não está disponível em outro campo, backup versionado ou documentação; a recuperação exige fonte oficial e intervenção auditada. O restante das colunas cifradas foi verificado e decifra corretamente.
- Nenhum commit foi criado nesta fase; o conjunto de alterações ainda depende do trabalho anterior de conta global/participantes.

### P1 — Fluxos essenciais incompletos

7. Conectar UI de candidaturas e convites em `MissionsPage`.
8. Conectar `LocationWorkflowModal` em `LocationsPage`.
9. Conectar upload/exibição de avatar em `AccountPage`.
10. Implementar criação de organizadora em `OrganizationsPage`.
11. Completar `AcademyAdminPage` (módulos, aulas, versões, publicação).
12. Substituir funções hardcoded do Passaporte por `/qualifications`.

### P2 — Robustez e DX

13. Introduzir `AuthContext`/cache de `/auth/me` e eliminar chamadas duplicadas.
14. Padronizar estados de loading/erro/vazio em todas as queries.
15. Padronizar chaves de cache React Query por área/contexto.
16. Corrigir redirect global de 401 no login.
17. Remover rotas de menu inexistentes ou implementá-las.
18. Externalizar `baseURL` via `VITE_API_URL` ou proxy.
19. Pinar dependências Python e incluir dependências de teste.
20. Adicionar testes de integração com PostgreSQL, concorrência e frontend.
21. Endurecer Docker (non-root, multi-stage, healthcheck) e compose (credenciais, bind local, Redis auth).
22. Adicionar revogação/refresh de JWT.

---

## 14. Conclusão

O OPERAN tem uma base sólida e moderna, com separação de camadas consistente, boa cobertura de segurança multi-tenant nos fluxos mais sensíveis e uma suíte de testes que protege as regras centrais de conta global, convites e missões. Os seis riscos P0 identificados na auditoria foram corrigidos e cobertos por testes: reativação indevida por convite, ausência de throttling, hashes de PII sem chave, promessa de MFA, concorrência na decisão de missões e bootstrap de admin. O produto, porém, ainda está em transição entre “backend maduro” e “frontend parcial”: várias funcionalidades já implementadas na API ainda não estão acessíveis na interface. O caminho recomendado é conectar os fluxos já existentes no frontend e, em seguida, evoluir Academia, indicadores, observabilidade, MFA e revogação de JWT.
