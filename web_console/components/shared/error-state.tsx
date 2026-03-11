export function ErrorState({
  title,
  message,
  onRetry
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <section className="state-banner" role="alert">
      <p>{title}</p>
      <p>{message}</p>
      {onRetry ? <button onClick={onRetry}>Retry</button> : null}
    </section>
  );
}
