export function SearchInput({
  value,
  onChange,
  placeholder = "Search..."
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      aria-label="Search tickets"
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      style={{
        width: "100%",
        padding: "10px 12px",
        borderRadius: 8,
        border: "1px solid var(--border)",
        background: "#fff"
      }}
    />
  );
}
