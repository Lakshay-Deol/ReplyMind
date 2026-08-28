import { createMindsClient } from '@animocabrands/minds-client-lib';
import { config } from './config.js';

export const mindsClient = createMindsClient({
    builderApiKey: config.MINDS_BUILDER_API_KEY
});

export const getMind = async (mindId: string) => {
    return await mindsClient.getMind(mindId);
};

export const getCognitionBalance = async (mindId: string) => {
    return await mindsClient.getCognitionBalance(mindId);
};
