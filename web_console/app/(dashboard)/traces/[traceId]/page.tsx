"use client";

import { useParams } from "next/navigation";
import { TraceGroundingCard } from "@/components/traces/trace-grounding-card";
import { TraceRoutingCard } from "@/components/traces/trace-routing-card";
import { TraceTimeline } from "@/components/traces/trace-timeline";
import { TraceToolCallsCard } from "@/components/traces/trace-tool-calls-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useTraceDetail } from "@/lib/hooks/useTraceDetail";

function toText(value: string | null | undefined) {
  return value && value.length > 0 ? value : "-";
}

export default function TraceDetailPage() {
  const params = useParams<{ traceId: string }>();
  const traceId = params?.traceId;

  if (!traceId) {
    return <ErrorState title="Invalid trace id." message="Cannot resolve trace from route." />;
  }

  const { loading, error, data, refetch } = useTraceDetail(traceId);

  if (loading) {
    return <LoadingState title="Trace detail is syncing." />;
  }

  if (error) {
    return <ErrorState title="Failed to load trace detail." message={error} onRetry={() => void refetch()} />;
  }

  if (!data) {
    return <EmptyState title="Trace not found." message={`No trace payload for ${traceId}.`} />;
  }

  return (
    <section>
      <h2 className="section-title">Trace Detail</h2>
      <article className="card">
        <h3>{data.trace_id}</h3>
        <div style={{ color: "var(--muted)", marginTop: 8 }}>
          ticket={toText(data.ticket_id)} · session={toText(data.session_id)}
        </div>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          workflow={toText(data.workflow)} · channel={toText(data.channel)} · provider={toText(data.provider)}
        </div>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          latency={data.latency_ms !== null ? `${data.latency_ms}ms` : "-"} · created_at={toText(data.created_at)}
        </div>
      </article>

      <div
        style={{
          marginTop: 12,
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))"
        }}
      >
        <TraceRoutingCard
          routeDecision={data.route_decision}
          handoff={data.handoff}
          handoffReason={data.handoff_reason}
          errorOnly={data.error_only}
        />
        <TraceToolCallsCard toolCalls={data.tool_calls} />
        <TraceGroundingCard retrievedDocs={data.retrieved_docs} summary={data.summary} />
      </div>

      <div style={{ marginTop: 12 }}>
        <TraceTimeline events={data.events} />
      </div>
    </section>
  );
}
