import { mindsClient } from './minds.js';
import { config } from './config.js';

export const findOrCreateConversation = async (alias: string) => {
    if (!config.MINDS_MIND_ID) {
        throw new Error("MINDS_MIND_ID is missing");
    }
    return await mindsClient.ensureConversation(alias, config.MINDS_MIND_ID);
};

export const sendMessageAndWait = async (alias: string, text: string) => {
    const afterFingerprint = await mindsClient.getLatestHistoryFingerprint(alias);
    
    await mindsClient.sendMessage({
        alias,
        messageText: text
    });
    
    const replyOutcome = await mindsClient.waitForReply({
        alias,
        timeoutMs: 45000,
        afterFingerprint
    });
    
    if (replyOutcome.timedOut) {
        throw new Error("Timeout waiting for Mind reply");
    }
    
    return replyOutcome.reply.messageText;
};

export const getHistory = async (alias: string) => {
    return await mindsClient.getHistory(alias);
};
