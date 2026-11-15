import redis from "../redis/client"
import { safeJsonParse } from "./safeJsonParse"

export async function getJsonKey(key: string) {
  const value = await redis.get(key)

  return safeJsonParse(value)
}

export async function getStringKey(key: string) {
  return await redis.get(key)
}

export async function getHashFields(key: string, fields: string[]) {
  const values = await redis.hmget(key, ...fields)
  const out: Record<string, string | null> = {}
  for (let i = 0; i < fields.length; i++) {
    out[fields[i]] = values[i]
  }
  return out
}
