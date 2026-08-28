import { timingSafeEqual } from 'node:crypto';

import express from 'express';
import cors from 'cors';
import { config } from './config.js';
import { findOrCreateConversation, sendMessageAndWait, getHistory } from './conversations.js';
import { getMind, getCognitionBalance } from './minds.js';

const app = express();
app.use(cors());

// Cheap liveness probe stays open; everything else is gated when a token is set.
app.use((req, res, next) => {
    if (!config.SERVICE_TOKEN || req.path === '/health') return next();
    const presented = req.get('x-replymind-token') || '';
    const expected = config.SERVICE_TOKEN;
    // Constant-time compare on equal-length buffers.
    const a = Buffer.from(presented);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !timingSafeEqual(a, b)) {
        return res.status(401).json({ error: 'unauthorized' });
    }
    next();
});

app.use(express.json());

app.get('/agent/status', async (req, res) => {
    try {
        // Independent upstream calls -- running them in parallel roughly halves
        // the round-trip, which the console renders on every page.
        const [mind, balRes] = await Promise.all([
            getMind(config.MINDS_MIND_ID),
            getCognitionBalance(config.MINDS_MIND_ID).catch((e: any) => {
                console.warn("Could not fetch cognition balance:", e.message);
                return null;
            }),
        ]);
        const balance = balRes?.cognition ?? null;
        res.json({
            status: 'ok',
            mindId: mind.mindId,
            name: mind.name,
            walletAddress: mind.walletAddress ?? null,
            chain: mind.chain ?? null,
            cognition: balance,
            email: mind.email ?? null
        });
    } catch (error: any) {
        res.status(500).json({ status: 'error', error: error.message });
    }
});

app.get('/agent/wallet', async (req, res) => {
    try {
        // Independent upstream calls -- running them in parallel roughly halves
        // the round-trip, which the console renders on every page.
        const [mind, balRes] = await Promise.all([
            getMind(config.MINDS_MIND_ID),
            getCognitionBalance(config.MINDS_MIND_ID).catch((e: any) => {
                console.warn("Could not fetch cognition balance:", e.message);
                return null;
            }),
        ]);
        const balance = balRes?.cognition ?? null;
        res.json({
            mindId: mind.mindId,
            name: mind.name,
            walletAddress: mind.walletAddress ?? null,
            chain: mind.chain ?? null,
            cognitionBalance: balance,
            status: 'active'
        });
    } catch (error: any) {
        res.status(500).json({ status: 'error', error: error.message });
    }
});

app.post('/agent/message', async (req, res) => {
    try {
        const { alias, message } = req.body;
        if (!alias || !message) {
            return res.status(400).json({ error: 'Missing alias or message' });
        }
        
        await findOrCreateConversation(alias);
        const reply = await sendMessageAndWait(alias, message);
        
        res.json({ reply });
    } catch (error: any) {
        console.error("Agent message error:", error);
        res.status(500).json({ error: error.message });
    }
});

app.get('/agent/history', async (req, res) => {
    try {
        const { alias } = req.query;
        if (!alias || typeof alias !== 'string') {
            return res.status(400).json({ error: 'Missing or invalid alias' });
        }
        
        const history = await getHistory(alias);
        res.json({ history });
    } catch (error: any) {
        res.status(500).json({ error: error.message });
    }
});

// Cheap liveness probe: no upstream call, so a platform health check never
// waits on the Minds API (which can take 15s to answer).
app.get('/health', (_req, res) => {
    res.json({ status: 'ok', mindId: config.MINDS_MIND_ID ? 'configured' : 'missing' });
});

app.listen(Number(config.PORT), '0.0.0.0', () => {
    console.log(`Minds Integration Service listening on port ${config.PORT}`);
});
