import { NavLink, Outlet, useLocation, Link } from "react-router-dom";

const navItems = [
  { to: "/categorias", label: "Categorías", icon: "🏷️", color: "bg-warning-500" },
  { to: "/ingredientes", label: "Ingredientes", icon: "🧂", color: "bg-success-500" },
  { to: "/productos", label: "Productos", icon: "📦", color: "bg-brand-500" },
];

const breadcrumbMap: Record<string, { label: string; path: string }> = {
  categorias: { label: "Categorías", path: "/categorias" },
  ingredientes: { label: "Ingredientes", path: "/ingredientes" },
  productos: { label: "Productos", path: "/productos" },
};

export default function Layout() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  // Build breadcrumb items
  const breadcrumbItems: { label: string; path?: string }[] = [];
  segments.forEach((seg, i) => {
    const mapped = breadcrumbMap[seg];
    if (mapped) {
      // If it's not the last segment, make it a link
      const isLast = i === segments.length - 1;
      breadcrumbItems.push({
        label: mapped.label,
        path: isLast ? undefined : mapped.path,
      });
    } else if (!isNaN(Number(seg))) {
      breadcrumbItems.push({ label: `Detalle #${seg}` });
    }
  });

  return (
    <div className="min-h-screen flex">
      {/* ─── Sidebar ─────────────────────────────── */}
      <aside className="w-60 bg-sidebar-900 flex flex-col shrink-0 sticky top-0 h-screen">
        {/* Logo */}
        <div className="px-5 py-6 border-b border-white/10">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-500 flex items-center justify-center shadow-lg shadow-brand-500/30">
              <span className="text-white font-bold text-xs">P4</span>
            </div>
            <span className="text-white font-semibold text-sm tracking-tight">
              Gestión de Productos
            </span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-5">
          <p className="px-3 mb-3 text-[10px] font-bold tracking-[0.15em] text-sidebar-500 uppercase">
            Módulos
          </p>
          <div className="space-y-1">
            {navItems.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? "bg-white/10 text-white shadow-sm"
                      : "text-sidebar-500 hover:text-white hover:bg-white/5"
                  }`
                }
              >
                <span
                  className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm ${link.color} text-white shadow-sm`}
                >
                  {link.icon}
                </span>
                {link.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </aside>

      {/* ─── Main content ────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar with breadcrumb */}
        <header className="bg-white border-b border-surface-200 sticky top-0 z-30">
          <div className="px-8 h-14 flex items-center">
            <div className="flex items-center gap-2 text-sm">
              {breadcrumbItems.map((item, i) => (
                <span key={i} className="flex items-center gap-2">
                  {i > 0 && <span className="text-surface-300">/</span>}
                  {item.path ? (
                    <Link
                      to={item.path}
                      className="text-surface-400 hover:text-brand-600 transition-colors"
                    >
                      {item.label}
                    </Link>
                  ) : (
                    <span className="text-surface-800 font-medium">
                      {item.label}
                    </span>
                  )}
                </span>
              ))}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-8 animate-page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
