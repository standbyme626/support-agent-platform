export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <section className="state-banner">
      <p>{title}</p>
      <p>{message}</p>
    </section>
  );
}
