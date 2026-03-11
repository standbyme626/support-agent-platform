export function LoadingState({ title }: { title: string }) {
  return (
    <section className="state-banner" role="status" aria-live="polite">
      <p>{title}</p>
      <p>Loading latest metrics...</p>
    </section>
  );
}
