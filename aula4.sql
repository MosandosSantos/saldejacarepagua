-- ============================================================
-- GPRBRCRM — Aula 4: adaptação pro nicho CLÍNICA / SAÚDE
-- ============================================================
\c gprbr

-- Novos campos do cadastro
ALTER TABLE contatos ADD COLUMN IF NOT EXISTS procedimento    TEXT DEFAULT '—';
ALTER TABLE contatos ADD COLUMN IF NOT EXISTS ultima_consulta TEXT DEFAULT '—';
ALTER TABLE contatos ADD COLUMN IF NOT EXISTS origem          TEXT DEFAULT '—';
ALTER TABLE contatos ADD COLUMN IF NOT EXISTS pagamento       TEXT DEFAULT '—';

-- Mapeamento das etapas antigas para o funil da clínica
UPDATE contatos SET stage = 'interessado'        WHERE stage = 'novo';
UPDATE contatos SET stage = 'avaliacao_agendada' WHERE stage = 'contato';
UPDATE contatos SET stage = 'avaliacao_feita'    WHERE stage = 'qualificado';
UPDATE contatos SET stage = 'orcamento'          WHERE stage IN ('proposta','negociacao');

-- Segmentos do nicho clínica
UPDATE contatos SET seg = 'estetica' WHERE seg IN ('clinica','agencia');
UPDATE contatos SET seg = 'odonto'   WHERE seg = 'advocacia';
UPDATE contatos SET seg = 'derma'    WHERE seg = 'imobiliaria';
UPDATE contatos SET seg = 'fisio'    WHERE seg = 'industria';
UPDATE contatos SET seg = 'nutri'    WHERE seg = 'educacao';
UPDATE contatos SET seg = 'geral'    WHERE seg = 'varejo';

-- Dados de exemplo do ramo (procedimento, última consulta, origem, pagamento)
UPDATE contatos SET procedimento='Harmonização facial',   ultima_consulta='2026-07-18', origem='Instagram',  pagamento='Particular' WHERE id=1;
UPDATE contatos SET procedimento='Implantes dentários',   ultima_consulta='2026-07-22', origem='Google',     pagamento='Convênio'   WHERE id=2;
UPDATE contatos SET procedimento='Limpeza de pele',       ultima_consulta='2026-07-25', origem='Indicação',  pagamento='Particular' WHERE id=3;
UPDATE contatos SET procedimento='Botox',                 ultima_consulta='2026-07-15', origem='WhatsApp',   pagamento='Particular' WHERE id=4;
UPDATE contatos SET procedimento='Preenchimento labial',  ultima_consulta='2026-06-30', origem='Instagram',  pagamento='Particular' WHERE id=5;
UPDATE contatos SET procedimento='Clareamento dental',    ultima_consulta='2026-07-28', origem='Google',     pagamento='Convênio'   WHERE id=6;
UPDATE contatos SET procedimento='Aparelho ortodôntico',  ultima_consulta='2026-07-10', origem='Indicação',  pagamento='Convênio'   WHERE id=7;
UPDATE contatos SET procedimento='Fisioterapia pós-op',   ultima_consulta='2026-07-19', origem='Google',     pagamento='Convênio'   WHERE id=8;
UPDATE contatos SET procedimento='Consulta dermatológica',ultima_consulta='2026-07-12', origem='Site',       pagamento='Particular' WHERE id=9;
UPDATE contatos SET procedimento='Limpeza de pele profunda',ultima_consulta='2026-07-26',origem='Instagram',  pagamento='Particular' WHERE id=10;
UPDATE contatos SET procedimento='Harmonização facial',   ultima_consulta='2026-07-08', origem='WhatsApp',   pagamento='Particular' WHERE id=11;
UPDATE contatos SET procedimento='Botox',                 ultima_consulta='2026-07-02', origem='Instagram',  pagamento='Particular' WHERE id=12;
UPDATE contatos SET procedimento='Peeling químico',       ultima_consulta='2026-07-21', origem='Google',     pagamento='Particular' WHERE id=13;
UPDATE contatos SET procedimento='Implantes dentários',   ultima_consulta='2026-07-11', origem='Indicação',  pagamento='Convênio'   WHERE id=14;
UPDATE contatos SET procedimento='Depilação a laser',     ultima_consulta='2026-07-27', origem='Instagram',  pagamento='Particular' WHERE id=15;
UPDATE contatos SET procedimento='Fisioterapia esportiva',ultima_consulta='2026-07-16', origem='Google',     pagamento='Convênio'   WHERE id=16;
UPDATE contatos SET procedimento='Nutrição clínica',      ultima_consulta='2026-07-05', origem='Indicação',  pagamento='Particular' WHERE id=17;
UPDATE contatos SET procedimento='Limpeza de pele',       ultima_consulta='2026-07-24', origem='WhatsApp',   pagamento='Particular' WHERE id=18;
UPDATE contatos SET procedimento='Clareamento dental',    ultima_consulta='2026-07-13', origem='Google',     pagamento='Convênio'   WHERE id=19;
UPDATE contatos SET procedimento='Harmonização facial',   ultima_consulta='2026-07-17', origem='Instagram',  pagamento='Particular' WHERE id=20;

-- Confirmação
SELECT stage, COUNT(*) AS qtd FROM contatos GROUP BY stage ORDER BY stage;
SELECT seg, COUNT(*) AS qtd FROM contatos GROUP BY seg ORDER BY seg;
