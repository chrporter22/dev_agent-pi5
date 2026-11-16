import { useSessions } from "../../hooks/useSessions"
import { useRetrySession } from "../../hooks/useRetrySession"
import Card from "../ui/Card"

function statusColor(status: string) {
  switch (status) {
    case "complete":
      return "text-[#35b779]"
    case "running":
      return "text-[#6cce59]"
    case "failed":
      return "text-[#ef4444]"
    case "queued":
      return "text-[#94a3b8]"
    default:
      return "text-muted"
  }
}

function formatTime(ts: number | null) {
  if (!ts) return "—"
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  })
}

function truncate(text: string | null, max: number) {
  if (!text) return null
  return text.length > max ? text.slice(0, max) + "…" : text
}

interface RetryButtonProps {
  jobId: string
  onRetried?: () => void
}

function RetryButton({ jobId, onRetried }: RetryButtonProps) {
  const retry = useRetrySession()

  const handleClick = () => {
    retry.mutate(jobId, {
      onSuccess: () => onRetried?.()
    })
  }

  const label = retry.isPending
    ? "Re-queuing…"
    : retry.isError
      ? "Retry failed"
      : retry.isSuccess
        ? "Re-queued"
        : "Retry"

  const classes = `
    text-[10px]
    font-mono
    uppercase
    tracking-wider
    px-2
    py-1
    rounded
    border
    transition-colors
    ${
      retry.isSuccess
        ? "border-[#35b779] text-[#35b779]"
        : retry.isError
          ? "border-red-500 text-red-400"
          : retry.isPending
            ? "border-muted text-muted cursor-wait"
            : "border-[#35b779] text-[#35b779] hover:bg-[#35b779] hover:text-[#0b0f14]"
    }
  `

  return (
    <button
      onClick={handleClick}
      disabled={retry.isPending || retry.isSuccess}
      className={classes}
    >
      {label}
    </button>
  )
}

export default function SessionLogs() {
  const { data: sessions, isLoading, error, refetch } = useSessions()

  return (
    <Card title="Session Logs">
      {isLoading && (
        <p className="text-muted text-sm">Loading…</p>
      )}
      {error && (
        <p className="text-red-400 text-sm">Failed to load sessions</p>
      )}
      {!isLoading && !error && (!sessions || sessions.length === 0) && (
        <p className="text-muted text-sm">No sessions recorded yet.</p>
      )}
      {!isLoading && !error && sessions && sessions.length > 0 && (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {sessions.map((session) => {
            const detail =
              session.type === "build"
                ? session.feature
                : truncate(session.text, 60)
            const resultText = session.error
              ? truncate(session.error, 100)
              : truncate(session.result, 100)
            const isFailed = session.status === "failed"

            return (
              <div
                key={session.id}
                className="
                  flex
                  items-start
                  gap-3
                  p-3
                  rounded-lg
                  bg-[#0b0f14]
                  border
                  border-border
                  text-xs
                "
              >
                <span
                  className={`
                    font-bold
                    w-16
                    shrink-0
                    ${statusColor(session.status)}
                  `}
                >
                  {session.status.toUpperCase()}
                </span>

                <div className="flex-1 min-w-0">
                  <div className="flex gap-2 items-center flex-wrap">
                    <span className="text-muted uppercase">
                      {session.type}
                    </span>
                    <span className="text-muted">·</span>
                    <span className="text-text font-mono">
                      {session.id}
                    </span>
                    {session.step && (
                      <>
                        <span className="text-muted">·</span>
                        <span className="text-muted">
                          {session.step}
                        </span>
                      </>
                    )}
                    <span className="text-muted">·</span>
                    <span className="text-muted">
                      {formatTime(session.createdAt)}
                    </span>
                    {isFailed && (
                      <span className="ml-auto">
                        <RetryButton jobId={session.id} onRetried={refetch} />
                      </span>
                    )}
                  </div>

                  {detail && (
                    <p className="text-text truncate mt-1" title={detail}>
                      {detail}
                    </p>
                  )}

                  {resultText && (
                    <p
                      className={`
                        mt-1
                        font-mono
                        ${session.error ? "text-red-400" : "text-muted"}
                      `}
                      title={session.error || session.result || ""}
                    >
                      {resultText}
                    </p>
                  )}

                  {session.prUrl && (
                    <a
                      href={session.prUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#35b779] hover:underline mt-1 block truncate"
                    >
                      PR: {session.prUrl}
                    </a>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
