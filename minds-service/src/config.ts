import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Try loading from local .env or parent .env
dotenv.config({ path: path.join(__dirname, '../.env') });
dotenv.config({ path: path.join(__dirname, '../../.env') });

export const config = {
    // Render (and most PaaS) inject PORT and health-check that exact port.
    // Binding MINDS_SERVICE_PORT only meant the service came up on 3001 and the
    // platform marked the deploy as failed.
    PORT: process.env.PORT || process.env.MINDS_SERVICE_PORT || 3001,
    MINDS_BUILDER_API_KEY: process.env.MINDS_BUILDER_API_KEY || '',
    MINDS_MIND_ID: process.env.MINDS_MIND_ID || '',
    // Shared secret between the console and this service. Required whenever the
    // service is reachable from the internet: it holds the Builder API key and
    // every /agent/message call spends the creator's cognition, so an open
    // instance is a way for strangers to drain their balance.
    SERVICE_TOKEN: process.env.MINDS_SERVICE_TOKEN || '',
};

if (!config.MINDS_BUILDER_API_KEY) {
    console.warn("WARNING: MINDS_BUILDER_API_KEY is not set.");
}
