import { z } from "zod";

export const CONTRACT_VERSION = "v1";

export const SERVED_MODELS = ["company-coder"] as const;
export type ServedModel = (typeof SERVED_MODELS)[number];

export const FINISH_REASONS = [
  "stop",
  "length",
  "content_filter",
  "tool_calls",
  "function_call",
] as const;
export const FinishReasonSchema = z.enum(FINISH_REASONS);
export type FinishReason = z.infer<typeof FinishReasonSchema>;

export const ChatRoleSchema = z.enum([
  "system",
  "developer",
  "user",
  "assistant",
  "tool",
  "function",
]);
export type ChatRole = z.infer<typeof ChatRoleSchema>;

export const ResponseMessageSchema = z.object({
  role: ChatRoleSchema,
  content: z.string().nullable(),
});
export type ResponseMessage = z.infer<typeof ResponseMessageSchema>;

export const ChoiceSchema = z.object({
  index: z.number().int().min(0),
  message: ResponseMessageSchema,
  finish_reason: FinishReasonSchema.optional().nullable(),
});
export type Choice = z.infer<typeof ChoiceSchema>;

export const UsageSchema = z.object({
  prompt_tokens: z.number().int().optional().nullable(),
  completion_tokens: z.number().int().optional().nullable(),
  total_tokens: z.number().int().optional().nullable(),
  prompt_cache_hit_tokens: z.number().int().optional().nullable(),
  prompt_cache_miss_tokens: z.number().int().optional().nullable(),
  completion_tokens_details: z
    .object({
      reasoning_tokens: z.number().int().optional().nullable(),
    })
    .optional()
    .nullable(),
});
export type Usage = z.infer<typeof UsageSchema>;

export const ChatCompletionResponseSchema = z.object({
  id: z.string(),
  object: z.literal("chat.completion"),
  created: z.number().int(),
  model: z.string(),
  system_fingerprint: z.string().optional().nullable(),
  choices: z.array(ChoiceSchema).min(1),
  usage: UsageSchema.optional().nullable(),
});
export type ChatCompletionResponse = z.infer<
  typeof ChatCompletionResponseSchema
>;

export const GatewayErrorResponseSchema = z.object({
  error: z.object({
    message: z.string(),
    type: z.string().optional().nullable(),
    code: z.string().optional().nullable(),
    param: z.string().optional().nullable(),
  }),
});
export type GatewayErrorResponse = z.infer<typeof GatewayErrorResponseSchema>;

export const ChatCompletionRequestSchema = z.object({
  model: z.enum(SERVED_MODELS),
  messages: z
    .array(
      z.object({
        role: ChatRoleSchema,
        content: z.string().nullable().optional(),
        name: z.string().optional(),
      })
    )
    .min(1),
});

export type ChatCompletionRequest = z.infer<typeof ChatCompletionRequestSchema>;
