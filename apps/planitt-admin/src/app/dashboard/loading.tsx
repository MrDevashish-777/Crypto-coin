export default function DashboardLoading() {
  return (
    <div className="space-y-3">
      <div className="h-8 w-64 bg-slate-800 rounded animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="h-28 bg-slate-900 border border-slate-800 rounded animate-pulse" />
        <div className="h-28 bg-slate-900 border border-slate-800 rounded animate-pulse" />
        <div className="h-28 bg-slate-900 border border-slate-800 rounded animate-pulse" />
      </div>
    </div>
  );
}

