export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>Support Ops Console</h1>
        <nav>
          <a href="/">Dashboard</a>
          <a href="/tickets">Tickets</a>
          <a href="/traces">Traces</a>
          <a href="/queues">Queues</a>
          <a href="/kb/faq">KB</a>
          <a href="/channels">Channels</a>
        </nav>
      </header>
      <main className="main-content">{children}</main>
    </div>
  );
}
