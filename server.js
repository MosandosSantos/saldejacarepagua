require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static(__dirname));

const pool = new Pool({
  user: process.env.PGUSER || 'postgres',
  host: process.env.PGHOST || 'localhost',
  database: process.env.PGDATABASE || 'cronoscrm',
  password: process.env.PGPASSWORD,
  port: parseInt(process.env.PGPORT || '5432', 10),
});

pool.on('connect', () => {});

/* ===================== ROTAS DA API ===================== */

// Lista todos os contatos
app.get('/api/contatos', async (req, res) => {
  try {
    const { rows } = await pool.query('SELECT * FROM contatos ORDER BY id');
    res.json(rows.map(function (r) { r.valor = parseFloat(r.valor); return r; }));
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

// Cria contato
app.post('/api/contatos', async (req, res) => {
  try {
    const b = req.body;
    const { rows } = await pool.query(
      'INSERT INTO contatos (nome, empresa, tel, email, seg, stage, valor, procedimento, ultima_consulta, origem, pagamento) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *',
      [b.nome, b.empresa || '—', b.tel || '—', b.email || '—', b.seg, b.stage, b.valor || 0, b.procedimento || '—', b.ultima_consulta || '—', b.origem || '—', b.pagamento || '—']
    );
    rows[0].valor = parseFloat(rows[0].valor);
    res.json(rows[0]);
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

// Atualiza contato (todos os campos)
app.put('/api/contatos/:id', async (req, res) => {
  try {
    const b = req.body;
    const { rows } = await pool.query(
      'UPDATE contatos SET nome=$1, empresa=$2, tel=$3, email=$4, seg=$5, stage=$6, valor=$7, procedimento=$8, ultima_consulta=$9, origem=$10, pagamento=$11, updated_at=NOW() WHERE id=$12 RETURNING *',
      [b.nome, b.empresa, b.tel, b.email, b.seg, b.stage, b.valor, b.procedimento || '—', b.ultima_consulta || '—', b.origem || '—', b.pagamento || '—', req.params.id]
    );
    if (!rows.length) return res.status(404).json({ error: 'nao encontrado' });
    rows[0].valor = parseFloat(rows[0].valor);
    res.json(rows[0]);
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

// Move de etapa
app.patch('/api/contatos/:id/stage', async (req, res) => {
  try {
    const { rows } = await pool.query(
      'UPDATE contatos SET stage=$1, updated_at=NOW() WHERE id=$2 RETURNING *',
      [req.body.stage, req.params.id]
    );
    if (!rows.length) return res.status(404).json({ error: 'nao encontrado' });
    rows[0].valor = parseFloat(rows[0].valor);
    res.json(rows[0]);
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

// Exclui contato
app.delete('/api/contatos/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM contatos WHERE id=$1', [req.params.id]);
    res.json({ ok: true });
  } catch (e) { console.error(e); res.status(500).json({ error: e.message }); }
});

/* ===================== FALLBACK ===================== */
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

/* ===================== START ===================== */
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log('CRMCronos.Cloud rodando em http://localhost:' + PORT);
});
