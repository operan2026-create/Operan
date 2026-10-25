# Instalação da skill OPERAN no Google Antigravity

## Instalação no projeto (recomendada)

1. Extraia o pacote.
2. Copie a pasta `.agents/skills/operan-project/` para a raiz do repositório OPERAN.
3. Confirme que o caminho final é:

   `.agents/skills/operan-project/SKILL.md`

4. Abra/recarregue o workspace no Antigravity.
5. Confira as skills disponíveis no painel de Customizations/Agent Skills. Você também pode chamar a skill pelo comando `/operan-project`, se suportado pela sua versão.

## Importante

- A skill é específica deste workspace e deve ser versionada junto ao projeto.
- Ela orienta o agente, mas não substitui testes, revisão humana nem controles reais de segurança.
- Antes de compartilhar o repositório, remova `.env`, tokens, chaves privadas e dados pessoais.
- O arquivo `references/project-map.md` é um mapa inicial; mantenha-o atualizado quando a arquitetura mudar.
