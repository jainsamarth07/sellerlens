interface Props {
  rows?: number;
  height?: number;
  className?: string;
}

export default function LoadingSkeleton({ rows = 3, height = 16, className = "" }: Props) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ height, width: `${85 - i * 10}%` }}
        />
      ))}
    </div>
  );
}
