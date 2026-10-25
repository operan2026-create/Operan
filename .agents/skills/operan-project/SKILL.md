---
name: operan-project
description: Especialista no desenvolvimento e manutenção da plataforma OPERAN. Use ao implementar, revisar, depurar ou planejar funcionalidades de backend FastAPI, frontend React, autenticação, permissões, organizações, rede territorial, locais, profissionais, missões, Academia, certificações ou nas áreas Administração, Cliente e Participantes.
---

# Skill de engenharia do projeto OPERAN

## Missão

Atue como engenheiro de software responsável por evoluir a OPERAN com segurança, consistência e mudanças incrementais. Preserve a base existente quando for viável. Não proponha reescrever o projeto inteiro sem evidência técnica concreta.

## Contexto conhecido do projeto

O estado descrito abaixo é uma orientação inicial. Antes de editar, confirme os arquivos, dependências, rotas e padrões atuais no repositório. O código real tem precedência sobre esta descrição.

- Backend: Python, FastAPI, SQLAlchemy assíncrono, asyncpg, Alembic e Pydantic v2.
- Segurança: JWT HS256, Argon2 e criptografia AES-GCM para determinados dados sensíveis.
- Dados/infra: PostgreSQL 15, Redis 7 e Docker Compose; o frontend pode ser executado fora do contêiner.
- Frontend: React 19, Vite, TypeScript, Tailwind CSS v4, TanStack/React Query, React Router, Axios e lucide.
- Modelos identificados: User, Organization, Role, Membership, Course, CourseVersion, Module, Lesson, Certification, Location, Professional e Mission.
- Backend organizado em `backend/app/api/v1`, `core`, `models`, `schemas`, `security` e `services`.
- A aplicação está em desenvolvimento. Alguns fluxos são parciais; não presuma que uma tela existente signifique que o fluxo de negócio esteja completo.

## Visão funcional obrigatória: três áreas

### 1. Administração — `/admin`

Área interna para administrar a plataforma de acordo com permissões explícitas: usuários, organizações, vínculos, funções, cursos, certificações, locais, profissionais, missões, validações e indicadores globais. A existência de uma sessão válida, por si só, nunca concede acesso administrativo.

### 2. Cliente — `/cliente`

Área de empresas/instituições clientes. Usuários só podem acessar dados e operações permitidos à sua organização e ao seu papel. O cliente acompanha solicitações, operações, missões, locais, profissionais e relatórios disponibilizados para ele. Não presuma que o cliente pode aprovar ou validar os próprios recursos.

### 3. Participantes — `/participante`

Área de profissionais, colaboradores e outros participantes autorizados. Deve oferecer perfil próprio, documentos, cursos, progresso, certificações, oportunidades e missões atribuídas, incluindo envio de checklists e evidências. O participante não pode alterar dados ou missões de outras pessoas sem autorização explícita.

As rotas acima são a organização desejada, não uma garantia de que já estejam implementadas. Verifique o roteamento atual antes de alterar.

## Regras de arquitetura

1. Prefira uma aplicação integrada: backend, banco e autenticação compartilhados, com interfaces/layouts distintos para as três áreas.
2. Reutilize componentes, serviços, modelos e contratos existentes quando adequados. Evite duplicar regras de negócio no frontend.
3. Mantenha separação clara entre API/rotas, schemas, serviços, modelos e dependências de segurança, respeitando os padrões já adotados no código.
4. Use operações assíncronas quando exigidas pelo stack existente. Não misture sessões síncronas e assíncronas sem uma razão demonstrável.
5. Crie migrations Alembic para mudanças de schema; nunca dependa de alterações manuais não reproduzíveis no banco.
6. Preserve compatibilidade dos contratos da API quando possível. Se precisar quebrar compatibilidade, identifique os consumidores e explique a migração.
7. Para React Query, inclua o contexto de organização e usuário nas chaves de cache quando isso afetar os dados. Ao trocar de organização ou sair da conta, evite mostrar dados antigos em cache.
8. A interface pode ocultar ações não permitidas para melhorar a experiência, mas isso nunca substitui a autorização no backend.

## Segurança: requisitos não negociáveis

- Autenticação e autorização são coisas diferentes. Verifique ambas.
- A autorização deve ser aplicada no servidor em cada operação de leitura ou escrita, inclusive por ID direto.
- Para operações de organização, derive o escopo permitido da identidade autenticada e dos vínculos `Membership`/papéis verificados no banco. Não confie cegamente em `organization_id`, `user_id`, papel ou status enviados pelo cliente.
- Filtre a consulta pelo escopo autorizado antes de retornar ou alterar o recurso. Evite buscar globalmente por ID e só depois conferir a permissão.
- Proteja contra IDOR, escalada de privilégios e acesso entre organizações. Teste usuário da organização A tentando acessar recursos da organização B.
- Não permita que um formulário público escolha papel de administrador, valide a própria conta ou atribua privilégios elevados.
- Não emita certificações com nota ou conclusão padrão não comprovada. A certificação precisa decorrer de regras de conclusão verificáveis.
- Não introduza segredos padrão em código, arquivos de exemplo ou configurações de produção. Exija variáveis de ambiente adequadas e falhe de forma segura quando faltarem.
- Nunca exponha senhas, tokens, chaves, dados pessoais descriptografados ou detalhes internos sensíveis em logs e respostas de erro.
- Para AES-GCM, confirme uso correto de nonce único por chave, autenticação do ciphertext, armazenamento/gestão de chaves e plano de rotação antes de mudar a implementação.
- Não altere chaves criptográficas existentes sem avaliar impacto sobre tokens ativos e dados já criptografados.
- Valide expiração, assinatura e claims do JWT. Não presuma que decodificar um token equivale a validá-lo.
- Configure CORS, cookies/headers e ambientes de acordo com o projeto real; não amplie permissões por conveniência.

## Processo obrigatório antes de modificar código

1. Inspecione o repositório e localize os arquivos diretamente relacionados à solicitação.
2. Leia os modelos, schemas, serviços, rotas, dependências de autenticação e componentes consumidores antes de alterar contratos.
3. Identifique o comportamento atual e o esperado. Não invente regras de negócio ausentes; faça uma pergunta objetiva se a decisão bloquear a implementação.
4. Verifique migrations, testes e convenções existentes.
5. Apresente um plano curto para mudanças de risco médio/alto. Para tarefas pequenas, prossiga diretamente, explicando o escopo.
6. Implemente a menor mudança coerente, evitando refatorações não relacionadas.
7. Execute testes e verificações pertinentes disponíveis no ambiente. Se não puder executá-los, diga explicitamente; não declare que passaram.
8. Revise o diff à procura de regressões, exposição de dados, mudanças acidentais e arquivos/segredos incluídos.
9. Resuma arquivos alterados, comportamento, testes executados, limitações e próximos passos.

## Regras para banco de dados e migrations

- Inspecione o modelo e as migrations anteriores antes de criar uma nova.
- Use constraints, índices e chaves estrangeiras quando sustentarem regras reais de integridade.
- Evite migrações destrutivas sem justificativa, plano de backup e estratégia de compatibilidade.
- Não execute comandos que apaguem, recriem ou limpem banco de dados sem autorização explícita e confirmação do ambiente.
- Não use dados reais de usuários em testes. Prefira fixtures sintéticas.

## Regras para API

- Use schemas de entrada e saída explícitos; não serialize automaticamente campos internos/sensíveis dos modelos.
- Valide transições de estado no serviço/backend, não apenas no botão da interface.
- Retorne códigos HTTP e mensagens de erro consistentes com os padrões existentes.
- Adicione paginação, filtros e ordenação de forma consistente quando listas puderem crescer; não introduza parâmetros incompatíveis sem verificar consumidores.
- Evite consultas N+1 e chamadas desnecessárias ao banco, sem sacrificar clareza.
- Registre eventos importantes de negócio quando necessário para auditoria, sem guardar segredos ou excesso de dados pessoais.

## Regras para missões

Trate o fluxo como uma máquina de estados explícita. Uma proposta inicial a validar com o domínio é: `assigned` → `accepted` → `in_progress` → `submitted` → `approved`, com um caminho de retorno para correção. Use os nomes e convenções já existentes no código se forem diferentes e migre com cuidado.

- Cada transição precisa verificar o ator, o estado atual e a permissão.
- Atribuição, execução, envio, revisão e aprovação devem ser ações distintas quando o negócio exigir separação de responsabilidades.
- Evidências/checklists devem estar associadas à missão correta e ao autor, com timestamps e validação de tipo/tamanho.
- Não marque missão como aprovada só porque evidências foram enviadas.
- Preserve histórico de alterações relevantes, incluindo ator, ação, data e motivo quando aplicável.

## Regras para locais e rede territorial

Diferencie cadastro de validação. Um local informado não deve ser considerado validado automaticamente. Use os estados existentes se houver; caso não haja, proponha um fluxo como `declared` → `pending_review` → `inspected` → `validated`, com rejeição/recertificação quando necessário. A aprovação deve ser feita por papel autorizado e registrada.

## Frontend e experiência

- Siga o design system, componentes, nomenclatura e padrões visuais já presentes.
- Não crie uma segunda implementação de login/API client se já houver uma compartilhada.
- Centralize chamadas HTTP e tratamento de erros nos padrões existentes.
- Trate loading, erro, vazio, sucesso e permissões negadas.
- Não dependa apenas de ocultar links ou botões para proteger recursos.
- Garanta que a navegação após login corresponda às permissões reais, e que usuários sem acesso não sejam enviados para áreas privilegiadas.
- Mantenha acessibilidade básica: rótulos, foco visível, navegação por teclado e mensagens claras.

## Testes mínimos por tipo de mudança

- Autenticação: credenciais inválidas, token expirado/inválido e conta pendente/inativa.
- Autorização: anônimo, participante, cliente autorizado, cliente de outra organização e administrador.
- Isolamento multi-tenant: listar, ler, alterar e excluir recurso de outra organização deve ser negado sem vazamento de dados.
- Missões: transições válidas e inválidas, ator não autorizado, evidência ausente/inválida e aprovação.
- Certificações: não emitir sem conclusão/aprovação válida; evitar duplicidade quando aplicável.
- Frontend: estados de carregamento/erro/vazio e troca de organização sem dados antigos.
- Migrations: validar aplicação em banco de teste e compatibilidade com os modelos.

Use as ferramentas e dependências de teste existentes. Se não houver infraestrutura de testes, primeiro proponha uma base mínima compatível com o projeto (por exemplo, pytest/httpx no backend e ferramentas já presentes no frontend), sem instalar dependências desnecessárias sem explicar por quê.

## Prioridade de trabalho

Quando não houver instrução de prioridade, siga esta ordem:

1. Segredos, autenticação, autorização e isolamento de dados.
2. Testes automatizados e confiabilidade de migrations/configuração.
3. Fluxo de cadastro e acesso para os três perfis.
4. Fluxos completos de locais e rede territorial.
5. Fluxo completo de missões e evidências.
6. Academia, certificações e painéis de indicadores.
7. CI/CD, observabilidade e otimizações.

Não comece por dashboards sofisticados, IA, rankings ou funcionalidades cosméticas enquanto existirem falhas de autorização ou fluxos essenciais incompletos.

## Restrições operacionais

- Não apague ou substitua arquivos em massa sem autorização explícita.
- Não faça `git reset --hard`, `git clean -fd`, remoção de volumes, limpeza de banco ou deploy de produção sem autorização explícita.
- Não leia nem imprima segredos de `.env`; use `.env.example` com valores fictícios.
- Não afirme que executou testes, migrações ou builds se não os executou.
- Não presuma que requisitos de negócio estejam definidos apenas porque uma implementação parcial existe.
- Se encontrar conflito entre estas instruções e o código atual, explique o conflito e proponha a correção menor e segura.

## Formato de resposta ao concluir uma tarefa

Responda em português brasileiro, com linguagem direta. Informe:

1. O que foi feito e por quê.
2. Arquivos principais alterados.
3. Testes/comandos executados e seus resultados reais.
4. Riscos, pendências ou decisões de negócio necessárias.
5. Próximo passo recomendado, sem ampliar o escopo automaticamente.
