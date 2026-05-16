import redis from "../redis/client"
import { safeJsonParse } from "./safeJsonParse"

export async function getJsonKey(key: string) {
  const value = await redis.get(key)

  return safeJsonParse(value)
}

export async function getStringKey(key: string) {
  return await redis.get(key)
}
