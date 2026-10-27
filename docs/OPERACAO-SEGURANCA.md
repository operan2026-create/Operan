# Operação de segurança — chaves, rate limiting e incidente de CNPJ

Documento operacional da Fase 1.1. Não contém segredos nem dados pessoais.

## 1. Chaves

| Chave | Uso | Onde deve viver |
|---|---|---|
| `SECRET_KEY` | assinatura JWT | secret manager / variável de ambiente |
| `CRYPTO_KEY` | AES-256-GCM de PII em repouso | secret manager / variável de ambiente |
| `PII_INDEX_KEY` | HMAC-SHA256 dos blind indexes de e-mail, CPF, RG e CNPJ | secret manager / variável de ambiente, **nunca no banco** |

- As três chaves devem ser distintas. A aplicação recusa iniciar se
  `PII_INDEX_KEY` for igual a `SECRET_KEY` ou `CRYPTO_KEY`.
- Nenhuma chave é escrita em logs, respostas ou no repositório. `backend/.env`
  é ignorado pelo Git; use `.env.example` apenas com placeholders.
- Perder `CRYPTO_KEY` torna os dados cifrados irrecuperáveis. Perder
  `PII_INDEX_KEY` não apaga dados, mas torna os índices existentes
  inconsultáveis até o recálculo.

### 1.1 Rotação de `PII_INDEX_KEY`

Não é necessário recifrar a PII: os valores continuam em `*_encrypted`. É
necessário recalcular todos os blind indexes.

Procedimento controlado (executar em janela de manutenção, com backup):

1. Fazer backup lógico das tabelas com índices: `users`, `invitations`,
   `person_profiles`, `professionals`, `organizations`,
   `participant_bank_accounts`, `participant_family_members`.
2. Definir a nova `PII_INDEX_KEY` no secret manager, mantendo a antiga
   disponível apenas durante a janela.
3. Executar um recálculo equivalente ao da migração `b8d2f4a6c9e1`
   (decifrar a PII com `CRYPTO_KEY` e regravar o HMAC com a nova chave).
   **Automação pendente:** hoje isso é feito por migração/script de
   manutenção; não existe comando dedicado no repositório.
4. Verificar: todos os hashes batem com o HMAC da PII decifrada; nenhum valor
   legado SHA-256 permanece; login e busca por CPF/e-mail funcionam.
5. Subir o backend com a nova chave e descartar a antiga do ambiente.
6. Registrar a rotação em auditoria (data, operador, tabelas, contagens).

Enquanto o recálculo não termina, a aplicação **não deve atender tráfego**:
metade dos índices com chave antiga e metade com a nova quebra buscas e login.

### 1.2 Rotação de `CRYPTO_KEY`

Procedimento mais delicado; exige recifrar cada coluna cifrada.

1. Backup lógico completo e teste de restauração.
2. Implantar código que consiga decifrar com a chave antiga e cifrar com a nova
   (janela de dupla chave) ou executar script offline de re-encryption.
3. Re-encifrar todas as colunas: `users.email_encrypted`,
   `organizations.cnpj_encrypted`, `professionals.*`, `person_profiles.*`,
   `participant_bank_accounts.*`, `participant_family_members.*`,
   `registration_drafts.data_encrypted`, `invitations.*`, `documents.file_name`.
4. Recalcular os blind indexes com `PII_INDEX_KEY` (a PII não mudou, mas a
   verificação deve ser refeita).
5. Verificar que nenhum valor decifrado retorna `[Encrypted Data]`.
6. Trocar a chave no secret manager e remover a antiga.

Não rotacione `CRYPTO_KEY` sem esse procedimento: os dados antigos ficam
ilegíveis. O fallback atual de `decrypt_data` retorna `[Encrypted Data]` em vez
de falhar alto; por isso a verificação explícita da etapa 5 é obrigatória.

## 2. Rate limiting de login

- Com `REDIS_URL` configurado, os contadores são compartilhados entre workers e
  instâncias. **Em produção com mais de um worker, Redis deve ser obrigatório**;
  o fallback em memória vale por processo e multiplica o limite efetivo pelo
  número de workers.
- Sem Redis, o limiter usa memória local (adequado a desenvolvimento e a uma
  única instância).
- `LOGIN_RATE_LIMIT_FAIL_OPEN=true` (padrão) permite login quando o backend de
  cache está indisponível. Para priorizar segurança sobre disponibilidade,
  definir `false`: nesse caso o login é recusado com 429 até o cache voltar.
- As operações Redis têm timeout de 1 s para não travar a rota de login.
- `TRUST_PROXY_HEADERS=true` só deve ser usado atrás de proxy reverso confiável;
  caso contrário, todas as requisições podem compartilhar o IP do proxy.
- Limitações residuais: um atacante pode bloquear temporariamente uma conta
  conhecida (DoS de lockout); cada tentativa bloqueada gera um `AuditLog`, o que
  pode amplificar escrita sob ataque. Monitorar e ajustar limites.

## 3. Incidente de CNPJ (Fase 1.1)

- Registro afetado: `organizations.id = 1dc879b5-0067-4f20-8d59-7b61c2ad9c6a`
  (`Fundacao Getulio Vargas`).
- `cnpj_encrypted` existe, mas não decifra com a `CRYPTO_KEY` atual nem com a
  chave padrão histórica do repositório. O ciphertext tem 42 bytes, compatível
  com nonce de 12 bytes + 14 caracteres + tag, ou seja, formato do
  `crypto_manager`; a falha é de **chave**, não de formato.
- A organização foi criada em 2026-09-08; o `.env` atual foi criado em
  2026-10-25. A hipótese mais provável é rotação/perda da chave anterior.
- O valor original **não existe em outro campo, backup versionado, seed ou
  documentação**. O `cnpj_hash` legado foi limpo pela migração porque não é
  usado em consultas.
- Varredura de todas as colunas cifradas populadas encontrou **apenas esse
  valor** indecifrável; usuários, convites, perfis e rascunhos estão legíveis.
- Recuperação segura (mediante autorização):
  1. Obter o CNPJ original em fonte oficial/autorizada (não inferir, não
     recalcular, não inventar).
  2. Em transação, gravar `cnpj_encrypted = crypto_manager.encrypt_data(cnpj)` e
     `cnpj_hash = cnpj_index(cnpj)`.
  3. Registrar evento de auditoria com operador, data, origem do dado e
     resultado, sem gravar o CNPJ em claro.
  4. Verificar decrypt + HMAC e registrar a evidência.
- O campo não é exposto em schema de resposta; a organização continua
  operacional sem CNPJ. Não apagar a organização nem outros dados.

## 4. Deploy controlado

```powershell
# 1. Backup lógico antes de qualquer migração
# 2. Configurar no ambiente/secret manager:
#    SECRET_KEY, CRYPTO_KEY, PII_INDEX_KEY, DATABASE_URL, REDIS_URL
# 3. Validar configuração (falha rápida se chave ausente/igual)
cd backend
.\venv\Scripts\python.exe -c "from app.core.config import settings; print('config ok')"

# 4. Migração em janela de manutenção
.\venv\Scripts\python.exe -m alembic current
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic current

# 5. Verificar hashes HMAC e login antes de liberar tráfego
# 6. Iniciar a API e validar /health
```

- A migração `b8d2f4a6c9e1` é DML (não altera schema), roda em transação no
  PostgreSQL e pode falhar de propósito se um e-mail/CPF não puder ser
  decifrado. Nesse caso, **não** force: corrija a chave/fonte do dado.
- Não executar `alembic downgrade` em produção. O downgrade local foi validado
  apenas como teste de reversibilidade.
- Em tabelas grandes, a migração mantém uma transação longa e atualiza linha a
  linha; planejar janela e monitorar locks.

## 5. Riscos residuais conhecidos

- MFA não implementado (apenas campo reservado).
- JWT sem revogação/refresh.
- `decrypt_data` silencia erros e retorna sentinela; consumidores precisam
  validar.
- `docker-compose.yml` expõe Postgres/Redis no host e usa credenciais locais
  literais; Redis sem autenticação.
- Dependências Python sem versões pinadas.
- Commit pendente: o conjunto atual de alterações inclui trabalho anterior de
  conta global/participantes, do qual as correções P0 dependem.
