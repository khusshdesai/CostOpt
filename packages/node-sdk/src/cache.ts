/**
 * In-Memory & Local Cache Helper for CostOpt Node.js SDK
 */

import crypto from 'crypto';
declare var Buffer: any;

export interface CachedResponse {
  response: any;
  createdAt: number;
}

export class MemoryCache {
  private cache: Map<string, CachedResponse>;

  constructor() {
    this.cache = new Map();
  }

  public getHash(text: str): string {
    return crypto.createHash('md5').update(text).digest('hex');
  }

  public get(promptText: string, model: string): any | null {
    const key = `${this.getHash(promptText)}||${model}`;
    const item = this.cache.get(key);
    if (!item) return null;
    return item.response;
  }

  public set(promptText: string, model: string, response: any): void {
    const key = `${this.getHash(promptText)}||${model}`;
    this.cache.set(key, {
      response,
      createdAt: Date.now(),
    });
  }

  public clear(): void {
    this.cache.clear();
  }
}
type str = string;
