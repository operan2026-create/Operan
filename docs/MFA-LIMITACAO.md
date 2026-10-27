# MFA — limitação atual (Fase 1)

## Situação

O OPERAN **não implementa autenticação multifator**. Os campos `mfa_enabled` e
`mfa_secret` existem no modelo `User` e `mfa_enabled` aparece em respostas de
API, mas:

- não há endpoint de configuração, confirmação, verificação ou recuperação;
- o login (`POST /api/v1/auth/login`) não possui segunda etapa;
- nenhuma tela do frontend oferece ou promete MFA;
- `mfa_secret` nunca é escrito pelo código atual e não está criptografado.

Portanto, `mfa_enabled` deve ser tratado apenas como **campo reservado**, nunca
como garantia de proteção ativa.

## O que foi feito nesta fase

- Documentação explícita da limitação (este arquivo).
- Comentário no modelo indicando que o campo é reservado e precisa ser
  criptografado antes de armazenar um segredo real.
- Teste de regressão que verifica que:
  - o login continua funcionando sem qualquer desafio de MFA;
  - o frontend não contém textos/telas que prometam MFA/2FA (o tipo
    `mfa_enabled` espelha apenas o contrato da API e não é exibido como
    proteção ativa).

## O que falta para ativar MFA com segurança

1. Definir o fator (TOTP é a opção mais simples) e as regras de recuperação.
2. Criptografar o segredo (AES-GCM, usando o gerenciador existente) ou usar um
   cofre de segredos; nunca armazenar em texto puro.
3. Endpoints: iniciar configuração, confirmar código, desativar, recuperar.
4. Login em duas etapas com token de curta duração entre a senha e o segundo
   fator, sem emitir o JWT final antes da verificação.
5. Códigos de recuperação de uso único, armazenados como hash.
6. UI de configuração e de desafio, com mensagens claras.
7. Testes de configuração, verificação, falha, bloqueio e recuperação.
8. Auditoria dos eventos de MFA sem registrar segredos ou códigos.

Enquanto os itens acima não forem concluídos, **não exibir MFA como ativo** em
nenhuma interface nem em relatórios de conformidade.

## Decisão de escopo

A implementação completa foi deliberadamente adiada nesta fase para não ampliar
o escopo de segurança sem revisão dedicada. A decisão registrada é: manter os
campos por compatibilidade, documentar a limitação e impedir promessas de
proteção inexistente.
