import { useCallback, useEffect, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BadgeIndianRupee, Bell, Boxes,
  Check, CircleAlert, ClipboardList, Download, Factory, FileText, Gauge,
  LayoutDashboard, LogOut, Menu, PackageCheck, Plus, Search, ShieldCheck, ShoppingBag,
  Users, X,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { download, getJson, postJson, putJson } from "./api";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "orders", label: "Orders & dispatch", icon: ShoppingBag },
  { id: "production", label: "Production", icon: Factory },
  { id: "inventory", label: "Inventory ledger", icon: Boxes },
  { id: "customers", label: "Customers & BOM", icon: Users },
  { id: "reports", label: "GST & reports", icon: FileText },
];
const roleUsers = [
  ["owner", "Owner"],
  ["admin", "Admin"],
  ["sales", "Salesman"],
  ["production", "Production Supervisor"],
  ["auditor", "Accountant/Auditor"],
];
const fmt = (value) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(Number(value || 0));
const rupees = (value) => `₹${fmt(value)}`;

function App() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("order-audit-user")); } catch { return null; }
  });
  const [view, setView] = useState("overview");
  const [data, setData] = useState(null);
  const [orders, setOrders] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [movements, setMovements] = useState([]);
  const [production, setProduction] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [bom, setBom] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [costing, setCosting] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [modal, setModal] = useState("");
  const [selectedOrder, setSelectedOrder] = useState(null);

  const refresh = useCallback(async () => {
    if (!localStorage.getItem("order-audit-token")) return;
    setError("");
    try {
      const [overview, orderData, stock, runs, customerData, productData, invoiceData, costData] = await Promise.all([
        getJson("/api/overview"), getJson("/api/orders"), getJson("/api/inventory"),
        getJson("/api/production"), getJson("/api/customers"), getJson("/api/products"),
        getJson("/api/invoices"), getJson("/api/costing"),
      ]);
      setData(overview);
      setOrders(orderData.orders);
      setInventory(stock.items);
      setMovements(stock.movements);
      setProduction(runs.runs);
      setCustomers(customerData.customers);
      setProducts(productData.products);
      setBom(productData.bom);
      setInvoices(invoiceData.invoices);
      setCosting(costData);
    } catch (reason) {
      setError(reason.message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh, user]);
  useEffect(() => {
    if (!notice && !error) return undefined;
    const timer = window.setTimeout(() => { setNotice(""); setError(""); }, 5000);
    return () => window.clearTimeout(timer);
  }, [notice, error]);

  const signIn = async (username, password) => {
    setBusy(true);
    setError("");
    try {
      const response = await postJson("/api/auth/login", { username, password });
      localStorage.setItem("order-audit-token", response.token);
      localStorage.setItem("order-audit-user", JSON.stringify(response.user));
      setUser(response.user);
      setNotice(`Welcome, ${response.user.display_name}`);
    } catch (reason) { setError(reason.message); }
    finally { setBusy(false); }
  };
  const signOut = () => {
    localStorage.removeItem("order-audit-token");
    localStorage.removeItem("order-audit-user");
    setUser(null);
    setData(null);
  };
  const act = async (callback, successMessage) => {
    setBusy(true);
    setError("");
    try {
      await callback();
      setNotice(successMessage);
      await refresh();
    } catch (reason) { setError(reason.message); }
    finally { setBusy(false); }
  };

  if (!user) return <Login onSignIn={signIn} busy={busy} error={error} />;
  const currentPage = navigation.find((item) => item.id === view);
  const changeView = (value) => { setView(value); setMobileNav(false); };
  return (
    <div className="min-h-screen bg-canvas text-ink">
      {mobileNav && <button aria-label="Close menu" onClick={() => setMobileNav(false)} className="fixed inset-0 z-30 bg-black/30 lg:hidden" />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[250px] flex-col border-r border-line bg-[#fbfaf7] transition-transform lg:translate-x-0 ${mobileNav ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-[84px] items-center gap-3 border-b border-line px-6">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-olive text-[17px] font-extrabold text-white">B.</div>
          <div><div className="font-display text-[15px] font-extrabold tracking-tight">batchline</div><div className="text-[9px] font-semibold uppercase tracking-[.19em] text-[#94958a]">Order to audit</div></div>
        </div>
        <div className="px-5 pt-7">
          <div className="mb-3 px-2 text-[10px] font-bold uppercase tracking-[.17em] text-[#a2a297]">WORKSPACE</div>
          <nav className="space-y-1">
            {navigation.map(({ id, label, icon: Icon }) => (
              <button key={id} onClick={() => changeView(id)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-[10px] text-left text-[13px] transition ${view === id ? "bg-[#edeee6] font-semibold text-olive" : "text-[#6e7168] hover:bg-[#f1f0eb]"}`}>
                <Icon size={16} strokeWidth={1.8} /><span className="flex-1">{label}</span>
                {id === "orders" && <span className="rounded-full bg-[#efe9dc] px-2 py-0.5 text-[10px] font-bold text-[#977b42]">{orders.filter((order) => order.status === "pending_review").length}</span>}
              </button>
            ))}
          </nav>
        </div>
        <div className="mt-auto p-4">
          <div className="rounded-xl border border-[#e9e5d8] bg-[#f7f4eb] p-3.5">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-[#6c6d61]"><ShieldCheck size={14} className="text-olive" />DEMO WORKSPACE</div>
            <p className="mb-2 mt-1.5 text-[11px] leading-5 text-[#89897f]">Seeded with the Murukku 200 g benchmark. No live customer data.</p>
            <button onClick={refresh} className="text-[11px] font-semibold text-olive hover:underline">Refresh data <ArrowRight size={12} className="ml-1 inline" /></button>
          </div>
          <div className="mt-4 flex items-center gap-3 border-t border-line px-2 pt-4">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-[#e7e8df] text-xs font-bold text-olive">{user.display_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}</div>
            <div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold">{user.display_name}</div><div className="truncate text-[10px] text-[#898b82]">{user.role}</div></div>
            <button title="Sign out" onClick={signOut} className="rounded-md p-1.5 text-[#96978f] hover:bg-[#eeede7] hover:text-ink"><LogOut size={15} /></button>
          </div>
        </div>
      </aside>

      <main className="min-h-screen lg:ml-[250px]">
        <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-line bg-[#f9f8f4]/95 px-5 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <button aria-label="Open menu" onClick={() => setMobileNav(true)} className="rounded-md p-2 text-[#73766d] hover:bg-[#efeee8] lg:hidden"><Menu size={18} /></button>
            <div className="text-xs text-[#96978d]">Operations <span className="px-1.5 text-[#c2c1b8]">/</span><span className="font-semibold text-[#454941]">{currentPage?.label}</span></div>
          </div>
          <div className="flex items-center gap-2 md:gap-4">
            <span className="hidden items-center gap-1.5 rounded-full border border-[#e5e3d9] bg-white px-2.5 py-1.5 text-[10px] font-semibold text-[#777a6e] sm:flex"><span className="h-1.5 w-1.5 rounded-full bg-[#798657]" />LOCAL DEMO</span>
            <button aria-label="Notifications" className="relative rounded-md p-2 text-[#82847b] hover:bg-[#efeee8]"><Bell size={17} /><span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[#c2954c]" /></button>
            <div className="hidden h-6 border-l border-line md:block" />
            <div className="hidden text-right sm:block"><div className="text-[11px] font-semibold">{user.role}</div><div className="text-[10px] text-[#94958a]">Role-based access</div></div>
            <div className="grid h-8 w-8 place-items-center rounded-full bg-olive text-[10px] font-bold text-white">{user.display_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}</div>
          </div>
        </header>

        <div className="mx-auto max-w-[1500px] px-5 pb-12 pt-7 md:px-8 md:pt-9">
          {error && <Toast kind="error" message={error} onClose={() => setError("")} />}
          {notice && <Toast kind="success" message={notice} onClose={() => setNotice("")} />}
          <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
            <div><div className="mb-1.5 text-[10px] font-bold uppercase tracking-[.19em] text-gold">TIRUCHIRAPPALLI FOODS · 18 NOV 2026</div><h1 className="font-display text-[25px] font-bold tracking-[-.04em] md:text-[29px]">{currentPage?.label}</h1><p className="mt-1 text-[12px] text-[#8b8d83]">{pageSubtitle(view)}</p></div>
            <div className="flex gap-2">
              {view === "production" && can(user, ["Production Supervisor", "Admin", "Owner"]) && <Button onClick={() => setModal("production")}><Plus size={14} />Record production</Button>}
              {view === "orders" && can(user, ["Salesman", "Admin", "Owner"]) && <Button onClick={() => setModal("order")}><Plus size={14} />New order</Button>}
              {view === "inventory" && can(user, ["Admin", "Owner"]) && <Button onClick={() => setModal("purchase")}><Plus size={14} />Record purchase</Button>}
              {view === "customers" && can(user, ["Admin", "Owner"]) && <Button onClick={() => setModal("customer")}><Plus size={14} />Add customer</Button>}
            </div>
          </div>
          {!data ? <Loading /> : (
            <>
              {view === "overview" && <Overview data={data} orders={orders} production={production} onNavigate={changeView} />}
              {view === "orders" && <OrdersView orders={orders} user={user} busy={busy} onApprove={(id) => act(() => postJson(`/api/orders/${id}/approve`, {}), "Order approved")} onReject={(id) => { const reason = window.prompt("Enter a reason for rejecting this order (at least 5 characters):"); if (reason !== null) act(() => postJson(`/api/orders/${id}/reject`, { reason }), "Order rejected"); }} onDispatch={(order) => { setSelectedOrder(order); setModal("dispatch"); }} onDownload={(id) => download(`/api/invoices/${id}/pdf`, "tax-invoice.pdf").catch((reason) => setError(reason.message))} />}
              {view === "production" && <ProductionView production={production} costing={costing} bom={bom} onInventory={() => changeView("inventory")} />}
              {view === "inventory" && <InventoryView inventory={inventory} movements={movements} />}
              {view === "customers" && <CustomersView customers={customers} products={products} bom={bom} user={user} busy={busy} onSaveProduct={(id, payload) => act(() => putJson(`/api/products/${id}`, payload), "Product master updated")} onSaveBom={(id, lines) => act(() => putJson(`/api/products/${id}/bom`, { lines }), "Bill of materials updated")} />}
              {view === "reports" && <ReportsView invoices={invoices} user={user} onExport={(name, format, month) => download(`/api/reports/export/${name}?format=${format}&month=${month}`, `${name}-${month}.${format}`).catch((reason) => setError(reason.message))} onInvoice={(id) => download(`/api/invoices/${id}/pdf`, "tax-invoice.pdf").catch((reason) => setError(reason.message))} onPayment={(invoice) => { setSelectedOrder(invoice); setModal("payment"); }} onCancel={(invoice) => { setSelectedOrder(invoice); setModal("cancel"); }} />}
            </>
          )}
        </div>
      </main>
      {modal && <WorkflowModal modal={modal} selected={selectedOrder} customers={customers} busy={busy} onClose={() => setModal("")} onSubmit={(path, payload, message) => act(async () => { await postJson(path, payload); setModal(""); }, message)} />}
    </div>
  );
}

function pageSubtitle(view) {
  return {
    overview: "A live read on orders, batch yield and the stock behind every dispatch.",
    orders: "Verify demand against finished stock before creating a GST invoice or dispatch.",
    production: "Record actual batch consumption and good output against the Murukku 200 g BOM.",
    inventory: "Every balance is derived from source-linked movements; posted ledger rows cannot be edited.",
    customers: "Demo accounts, product master and the standard bill of materials.",
    reports: "Sales, GST, production and payment records ready for audit and export.",
  }[view];
}

function can(user, roles) { return roles.includes(user.role); }

function Login({ onSignIn, busy, error }) {
  const [username, setUsername] = useState("owner");
  const [password, setPassword] = useState("demo123");
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f6f5f0] p-5">
      <div className="grid w-full max-w-[900px] overflow-hidden rounded-2xl border border-[#e8e5db] bg-white shadow-card md:grid-cols-[1.05fr_.95fr]">
        <div className="flex min-h-[530px] flex-col justify-between bg-[#515c41] p-8 text-white md:p-11">
          <div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 font-display text-lg font-extrabold">B.</div><div><div className="font-display font-bold">batchline</div><div className="text-[9px] uppercase tracking-[.2em] text-white/55">Order to audit</div></div></div>
          <div><div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[9px] font-bold tracking-[.13em] text-[#e2d5ae]"><Activity size={12} /> NIT TRICHY · INTERNSHIP PROJECT</div><h1 className="max-w-sm font-display text-[34px] font-semibold leading-[1.13] tracking-[-.045em]">From batch sheet to <span className="text-[#d6c38c]">balance sheet.</span></h1><p className="mt-4 max-w-sm text-[13px] leading-6 text-white/65">One connected view of the small-batch decisions that move a food business forward.</p></div>
          <div className="flex items-center gap-2 text-[10px] text-white/50"><ShieldCheck size={14} />Sandbox data · No real customer records</div>
        </div>
        <div className="p-8 md:p-11">
          <div className="mb-8"><h2 className="font-display text-[22px] font-bold tracking-tight">Welcome back</h2><p className="mt-1 text-[12px] text-[#92938b]">Sign in to the local demonstration workspace.</p></div>
          {error && <Toast kind="error" message={error} />}
          <form onSubmit={(event) => { event.preventDefault(); onSignIn(username, password); }}>
            <label className="mb-1.5 block text-[11px] font-semibold text-[#5b5e55]">Demo account</label>
            <select value={username} onChange={(event) => setUsername(event.target.value)} className="mb-4 w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[12px] outline-none focus:border-olive">
              {roleUsers.map(([id, label]) => <option value={id} key={id}>{label}</option>)}
            </select>
            <label className="mb-1.5 block text-[11px] font-semibold text-[#5b5e55]">Password</label>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[12px] outline-none focus:border-olive" />
            <button disabled={busy} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-olive py-3 text-[12px] font-semibold text-white transition hover:bg-[#56613f] disabled:opacity-60">{busy ? "Signing in..." : "Continue"}<ArrowRight size={14} /></button>
          </form>
          <div className="mt-6 rounded-lg border border-[#eeece4] bg-[#faf9f5] p-3 text-[10px] leading-5 text-[#8a8b81]"><span className="font-semibold text-[#62655c]">Demo password:</span> demo123 <span className="px-1">·</span> Each role has a separate account.</div>
        </div>
      </div>
    </div>
  );
}

function Overview({ data, orders, production, onNavigate }) {
  const summary = data.summary;
  const latestRun = production[0];
  const batchComparison = latestRun ? [{
    batch: latestRun.run_number,
    planned: Number(latestRun.expected_packets),
    actual: Number(latestRun.actual_good_packets),
  }] : [];
  const materials = data.raw_materials.map((row) => ({
    ...row, label: ({ "RM-FLOUR": "Flour", "RM-OIL": "Oil", "RM-SPICE": "Spice mix" })[row.item_code],
    unit: ({ "RM-FLOUR": "kg", "RM-OIL": "L", "RM-SPICE": "kg" })[row.item_code],
    max: ({ "RM-FLOUR": 200, "RM-OIL": 30, "RM-SPICE": 8 })[row.item_code],
  }));
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Finished stock" value={`${fmt(summary.finished_stock)} pkts`} icon={PackageCheck} foot="88 available after Retailer A dispatch" color="olive" />
        <Metric label="Open order checks" value={String(summary.open_orders).padStart(2, "0")} icon={ClipboardList} foot="Distributor B · 32 packets short" color="gold" />
        <Metric label="Outstanding" value={rupees(summary.outstanding)} icon={BadgeIndianRupee} foot="Retailer A · invoice INV-2026-001" color="slate" />
        <Metric label="Latest batch yield" value={`${fmt(100 + summary.production_yield)}%`} icon={Gauge} foot="−6% against planned 200 packets" color="terracotta" />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.65fr_1fr]">
        <section className="rounded-xl border border-line bg-white p-5 shadow-card md:p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><div className="font-display text-[14px] font-bold">Planned vs actual output</div><div className="mt-1 text-[10px] text-[#999a90]">Latest recorded production run · finished packets</div></div><div className="flex gap-4 text-[10px]"><Legend color="#c6a665" label="Expected" /><Legend color="#7c8861" label="Good output" /></div></div>
          <div className="h-[210px] w-full">
            <ResponsiveContainer width="100%" height="100%"><BarChart data={batchComparison} margin={{ left: -18, right: 4, top: 8, bottom: 0 }} barGap={9}>
              <CartesianGrid vertical={false} stroke="#efeee8" strokeDasharray="3 4" /><XAxis dataKey="batch" axisLine={false} tickLine={false} /><YAxis axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 9, border: "1px solid #e9e7df", fontSize: 11 }} />
              <Bar dataKey="planned" name="Expected" fill="#c6a665" radius={[4, 4, 0, 0]} maxBarSize={38} />
              <Bar dataKey="actual" name="Good output" fill="#7c8861" radius={[4, 4, 0, 0]} maxBarSize={38} />
            </BarChart></ResponsiveContainer>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#f1f0ec] pt-3 text-[10px] text-[#898b82]"><span>Batch RUN-2026-001 · 188 good packets</span><button onClick={() => onNavigate("production")} className="font-semibold text-olive">View production <ArrowRight className="ml-1 inline" size={12} /></button></div>
        </section>
        <section className="rounded-xl border border-line bg-white p-5 shadow-card md:p-6">
          <div className="mb-5 flex items-center justify-between"><div><div className="font-display text-[14px] font-bold">Material on hand</div><div className="mt-1 text-[10px] text-[#999a90]">Ledger-derived stock balance</div></div><button onClick={() => onNavigate("inventory")} className="rounded-md p-1.5 text-[#91938a] hover:bg-[#f5f4ef]"><ArrowRight size={15} /></button></div>
          <div className="space-y-5">{materials.map((item) => {
            const value = Number(item.balance);
            return <div key={item.item_code}><div className="mb-2 flex items-center justify-between text-[11px]"><span className="font-medium text-[#555950]">{item.label}</span><span className="font-semibold">{fmt(value)} <span className="font-normal text-[#9a9b91]">{item.unit}</span></span></div><div className="h-1.5 overflow-hidden rounded-full bg-[#f1f0eb]"><div className="h-full rounded-full bg-[#899372]" style={{ width: `${Math.min(100, value / item.max * 100)}%` }} /></div></div>;
          })}</div>
          <div className="mt-5 rounded-lg bg-[#f8f6f0] px-3 py-2.5 text-[10px] leading-4 text-[#797a70]"><span className="font-bold text-[#62664f]">Flour includes purchase:</span> 60 kg × ₹45/kg · closing 120 kg</div>
        </section>
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        <section className="rounded-xl border border-line bg-white shadow-card">
          <div className="flex items-center justify-between border-b border-[#efeee8] px-5 py-4"><div><div className="font-display text-[13px] font-bold">Order-to-cash queue</div><div className="mt-0.5 text-[10px] text-[#999a90]">Orders needing a check before stock moves</div></div><button onClick={() => onNavigate("orders")} className="text-[10px] font-semibold text-olive">All orders <ArrowRight className="ml-1 inline" size={12} /></button></div>
          <div className="divide-y divide-[#f1f0ec]">
            {orders.slice(0, 3).map((order) => (
              <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <div className="flex min-w-[190px] items-center gap-3"><div className="grid h-8 w-8 place-items-center rounded-lg bg-[#f3f1e9] text-olive"><ShoppingBag size={14} /></div><div><div className="text-[11px] font-semibold">{order.customer_name}</div><div className="mt-0.5 text-[9px] text-[#96978e]">{order.order_number} · {order.quantity} packets</div></div></div>
                <div className="flex items-center gap-3"><Status status={order.status} /><span className="hidden text-[10px] text-[#898b81] sm:inline">{order.status === "pending_review" ? "Stock review" : order.invoice_total ? rupees(order.invoice_total) : "Approved"}</span></div>
              </div>
            ))}
          </div>
        </section>
        <section className="rounded-xl border border-[#eadfcb] bg-[#f7f2e7] p-5 shadow-card">
          <div className="flex items-start gap-3"><div className="rounded-lg bg-[#eee5d3] p-2 text-[#a28248]"><CircleAlert size={16} /></div><div><div className="font-display text-[13px] font-bold text-[#554d3c]">Stock check before approval</div><p className="mt-1.5 text-[10px] leading-5 text-[#827963]">Distributor B requested <b>120 packets</b>. Only <b>88 packets</b> remain after Retailer A's dispatch.</p></div></div>
          <div className="my-4 flex items-end justify-between border-y border-[#e9dfcd] py-3"><span className="text-[10px] font-medium text-[#7d735f]">Shortfall</span><span className="font-display text-[22px] font-bold text-[#92723d]">32 <span className="text-[10px] font-medium">packets</span></span></div>
          <div className="text-[9px] leading-4 text-[#8c806a]">If invoiced interstate, Karnataka supply attracts IGST. Approval and dispatch remain blocked until stock is available.</div>
          <button onClick={() => onNavigate("orders")} className="mt-3 text-[10px] font-bold text-[#826a3f] hover:underline">Review Distributor B order <ArrowRight className="ml-1 inline" size={12} /></button>
        </section>
      </div>
      <section className="rounded-xl border border-line bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-[#efeee8] px-5 py-4"><div><div className="font-display text-[13px] font-bold">Benchmark production run</div><div className="mt-0.5 text-[10px] text-[#999a90]">RUN-2026-001 · Murukku 200 g · actual consumption vs standard</div></div><button onClick={() => onNavigate("production")} className="text-[10px] font-semibold text-olive">Run details <ArrowRight className="ml-1 inline" size={12} /></button></div>
        <VarianceTable run={production[0]} />
      </section>
    </div>
  );
}

function Metric({ label, value, icon: Icon, foot, color }) {
  const palette = { olive: "bg-[#eef0e8] text-olive", gold: "bg-[#f4efe4] text-[#a8874b]", slate: "bg-[#edf0ef] text-[#63706a]", terracotta: "bg-[#f4ece7] text-[#a5785d]" };
  return <div className="rounded-xl border border-line bg-white p-4 shadow-card md:p-[18px]"><div className="flex items-center justify-between"><span className="text-[10px] font-semibold text-[#888a80]">{label}</span><span className={`rounded-lg p-2 ${palette[color]}`}><Icon size={15} /></span></div><div className="mt-3 font-display text-[23px] font-bold tracking-[-.035em]">{value}</div><div className="mt-1.5 truncate text-[9px] text-[#92948b]">{foot}</div></div>;
}
function Legend({ color, label }) { return <span className="flex items-center gap-1.5 text-[#7e8077]"><i className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />{label}</span>; }

function VarianceTable({ run }) {
  if (!run) return <div className="p-6 text-[12px] text-[#898b82]">No production run recorded.</div>;
  const variance = (actual, planned) => planned
    ? `${Number(actual / planned * 100 - 100) > 0 ? "+" : ""}${fmt(actual / planned * 100 - 100)}%`
    : "—";
  const rows = [
    ["Good packets", `${run.expected_packets} packets`, `${fmt(run.actual_good_packets)} packets`, `${fmt(run.yield_variance_percent)}%`, Number(run.yield_variance_percent) < 0],
    ["Flour", `${fmt(run.planned?.flour_kg)} kg`, `${fmt(run.flour_kg)} kg`, variance(Number(run.flour_kg), Number(run.planned?.flour_kg)), false],
    ["Oil", `${fmt(run.planned?.oil_litres)} L`, `${fmt(run.oil_litres)} L`, variance(Number(run.oil_litres), Number(run.planned?.oil_litres)), Number(run.oil_variance_percent) > 0],
    ["Spice mix", `${fmt(run.planned?.spice_kg)} kg`, `${fmt(run.spice_kg)} kg`, variance(Number(run.spice_kg), Number(run.planned?.spice_kg)), false],
  ];
  return <div className="overflow-x-auto"><table className="w-full min-w-[500px] text-left"><thead><tr className="text-[9px] font-semibold uppercase tracking-[.1em] text-[#a0a097]"><th className="px-5 py-3">Measure</th><th className="px-5 py-3">BOM plan</th><th className="px-5 py-3">Actual</th><th className="px-5 py-3">Variance</th></tr></thead><tbody>{rows.map(([name, plan, actual, varianceLabel, isRisk]) => <tr key={name} className="border-t border-[#f1f0ec] text-[10px]"><td className="px-5 py-3 font-semibold">{name}</td><td className="px-5 py-3 text-[#81837a]">{plan}</td><td className="px-5 py-3">{actual}</td><td className="px-5 py-3"><span className={`rounded-full px-2 py-1 font-semibold ${isRisk ? "bg-[#f6eee7] text-[#9a7359]" : "bg-[#eff0ea] text-[#687453]"}`}>{varianceLabel}</span></td></tr>)}</tbody></table><div className="border-t border-[#f1f0ec] px-5 py-3 text-[9px] text-[#96978e]">Packaging: {run.actual_good_packets + run.damaged_pouches} pouches consumed ({run.actual_good_packets} good + {run.damaged_pouches} damaged) · {run.cartons_used} cartons</div></div>;
}

function OrdersView({ orders, user, busy, onApprove, onReject, onDispatch, onDownload }) {
  const [query, setQuery] = useState("");
  const filtered = orders.filter((order) => `${order.customer_name} ${order.order_number}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="rounded-xl border border-line bg-white shadow-card">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#efeee8] p-4 md:px-5"><div><div className="font-display text-[13px] font-bold">Sales orders</div><div className="mt-1 text-[10px] text-[#999a90]">Stock availability is checked again inside each dispatch transaction.</div></div><div className="relative"><Search className="absolute left-2.5 top-2.5 text-[#a3a49b]" size={13} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find an order..." className="w-48 rounded-lg border border-[#e9e7df] py-2 pl-8 pr-3 text-[10px] outline-none focus:border-olive" /></div></div>
    <div className="overflow-x-auto"><table className="w-full min-w-[860px] text-left"><thead><tr className="bg-[#fbfaf7] text-[9px] font-semibold uppercase tracking-[.1em] text-[#9b9c92]">{["Order / customer", "Destination", "Qty & price", "Availability", "Tax", "Status", "Actions"].map((item) => <th className="px-4 py-3.5" key={item}>{item}</th>)}</tr></thead><tbody>
      {filtered.map((order) => <tr className="border-t border-[#f0efe9] text-[10px]" key={order.id}>
        <td className="px-4 py-4"><div className="font-semibold">{order.order_number}</div><div className="mt-1 text-[#92948a]">{order.customer_name}</div></td>
        <td className="px-4 py-4"><div>{order.customer_state}</div><div className="mt-1 text-[9px] text-[#999a91]">{order.state_code === "33" ? "Intrastate" : "Interstate"}</div></td>
        <td className="px-4 py-4"><div>{order.quantity} packets</div><div className="mt-1 text-[#92948a]">{rupees(order.unit_price)} / packet</div></td>
        <td className="px-4 py-4">{order.shortage > 0 ? <span className="rounded-full bg-[#f7eee7] px-2 py-1 font-semibold text-[#a16c4e]">Short {order.shortage}</span> : <span className="font-semibold text-olive">{fmt(order.available_stock)} in stock</span>}</td>
        <td className="px-4 py-4"><span className="rounded-full bg-[#f4f2ec] px-2 py-1 text-[9px] text-[#77796f]">{order.tax_treatment}</span></td>
        <td className="px-4 py-4"><Status status={order.status} /></td>
        <td className="px-4 py-4">{order.status === "dispatched" ? <button onClick={() => onDownload(order.invoice_id)} className="inline-flex items-center gap-1 text-[9px] font-semibold text-olive hover:underline"><FileText size={12} />Invoice</button> : order.status === "pending_review" && can(user, ["Admin", "Owner"]) ? <div className="flex gap-1.5"><button disabled={busy || order.shortage > 0} onClick={() => onApprove(order.id)} className="rounded-md border border-[#e6e5dc] px-2.5 py-1.5 text-[9px] font-semibold text-[#62665a] hover:bg-[#f7f6f1] disabled:cursor-not-allowed disabled:opacity-40">{order.shortage > 0 ? "Short stock" : "Approve"}</button><button disabled={busy} onClick={() => onReject(order.id)} className="rounded-md border border-[#eadbd4] px-2.5 py-1.5 text-[9px] font-semibold text-[#9a6954] hover:bg-[#fbf1ed] disabled:opacity-40">Reject</button></div> : order.status === "approved" && can(user, ["Admin", "Owner"]) ? <button onClick={() => onDispatch(order)} className="rounded-md bg-olive px-2.5 py-1.5 text-[9px] font-semibold text-white hover:bg-[#586342]">Dispatch</button> : <span className="text-[#a1a198]">—</span>}</td>
      </tr>)}
    </tbody></table></div>
    <div className="flex items-center justify-between border-t border-[#efeee8] px-5 py-3 text-[9px] text-[#98998f]"><span>Showing {filtered.length} benchmark orders</span><span>Review → approve → dispatch → tax invoice</span></div>
  </div>;
}

function Status({ status }) {
  const definitions = {
    dispatched: ["Dispatched", "bg-[#edf1ea] text-[#61724f]"],
    approved: ["Approved", "bg-[#edf1ea] text-[#61724f]"],
    pending_review: ["Needs review", "bg-[#f6f0e5] text-[#987c49]"],
    rejected: ["Rejected", "bg-[#f5ece9] text-[#a06e5a]"],
    cancelled: ["Cancelled", "bg-[#f5ece9] text-[#a06e5a]"],
    posted: ["Posted", "bg-[#edf1ea] text-[#61724f]"],
  };
  const [label, classes] = definitions[status] || [status, "bg-[#f1f0eb] text-[#7a7c73]"];
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[9px] font-semibold ${classes}`}><i className="h-1 w-1 rounded-full bg-current" />{label}</span>;
}

function ProductionView({ production, costing, bom, onInventory }) {
  const run = production[0];
  const itemName = { "RM-FLOUR": "Flour", "RM-OIL": "Oil", "RM-SPICE": "Spice", "PK-POUCH": "Pouch", "PK-CARTON": "Carton" };
  return <div className="space-y-5">
    <div className="grid gap-3 sm:grid-cols-3">
      <Metric label="Good output" value={`${fmt(run?.actual_good_packets)} pkts`} icon={PackageCheck} foot={`${fmt(run?.expected_packets)} expected packets`} color="olive" />
      <Metric label="Yield variance" value={`${fmt(run?.yield_variance_percent)}%`} icon={ArrowDownRight} foot={`${fmt((run?.expected_packets || 0) - (run?.actual_good_packets || 0))} packets from plan`} color="terracotta" />
      <Metric label="Oil consumption variance" value={`${Number(run?.oil_variance_percent) > 0 ? "+" : ""}${fmt(run?.oil_variance_percent)}%`} icon={Activity} foot={`${fmt(run?.oil_litres)} L actual vs ${fmt(run?.planned?.oil_litres)} L planned`} color="gold" />
    </div>
    <section className="rounded-xl border border-line bg-white shadow-card">
      <div className="flex items-center justify-between border-b border-[#efeee8] px-5 py-4"><div><div className="font-display text-[13px] font-bold">Production runs</div><div className="mt-1 text-[10px] text-[#999a90]">Consumption and output movements post together, or not at all.</div></div><button onClick={onInventory} className="text-[10px] font-semibold text-olive">Stock ledger <ArrowRight className="ml-1 inline" size={12} /></button></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left"><thead><tr className="bg-[#fbfaf7] text-[9px] uppercase tracking-[.1em] text-[#9b9c92]">{["Run", "Date", "Expected", "Good output", "Flour", "Oil", "Spice", "Packaging"].map((x) => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{production.map((row) => <tr key={row.id} className="border-t border-[#f0efe9] text-[10px]"><td className="px-4 py-4 font-semibold">{row.run_number}</td><td className="px-4 py-4 text-[#85877e]">{row.created_at.slice(0, 10)}</td><td className="px-4 py-4">{row.expected_packets} pkts</td><td className="px-4 py-4"><span className="font-semibold">{row.actual_good_packets} pkts</span><div className="mt-1 text-[9px] text-[#a17257]">−{row.expected_packets - row.actual_good_packets} variance</div></td><td className="px-4 py-4">{fmt(row.flour_kg)} kg</td><td className="px-4 py-4">{fmt(row.oil_litres)} L</td><td className="px-4 py-4">{fmt(row.spice_kg)} kg</td><td className="px-4 py-4">{row.actual_good_packets + row.damaged_pouches} pouches · {row.cartons_used} cartons</td></tr>)}</tbody></table></div>
      {run && <VarianceTable run={run} />}
    </section>
    <div className="grid gap-4 md:grid-cols-3">
      <div className="rounded-xl border border-line bg-white p-5"><div className="flex items-center gap-2 font-display text-[12px] font-bold"><BadgeIndianRupee size={15} className="text-olive" />Known material cost / good packet</div><div className="mt-3 font-display text-[23px] font-bold">{rupees(costing?.known_cost_per_good_packet)}</div><p className="mt-2 text-[9px] leading-4 text-[#898b82]">{costing?.complete ? "Material prices recorded. Excludes opening-stock valuation, labor, energy and overhead." : `Partial: missing latest rates for ${(costing?.missing_costs || []).join(", ")}. Opening-stock valuation and conversion costs are also excluded.`}</p></div>
      <div className="rounded-xl border border-line bg-white p-5"><div className="mb-3 flex items-center gap-2 font-display text-[12px] font-bold"><ClipboardList size={15} className="text-olive" />Standard BOM · per packet</div><p className="mb-3 text-[10px] leading-5 text-[#898b82]">Planned quantities come from the current product bill of materials.</p><div className="flex flex-wrap gap-2">{bom.map((line) => <span key={line.item_code} className="rounded-md bg-[#f5f4ef] px-2.5 py-1.5 text-[9px]"><b>{itemName[line.item_code] || line.ingredient}</b> · {fmt(line.quantity_per_packet)} {line.unit}</span>)}</div></div>
      <div className="rounded-xl border border-[#e7e4d8] bg-[#f5f3eb] p-5"><div className="font-display text-[12px] font-bold">Variance is traceable</div><p className="mt-2 text-[10px] leading-5 text-[#818277]">Every production run is linked to its raw-material issues, packaging use and good output in the stock ledger. Correct a posted run with a reversing transaction—not by overwriting its quantities.</p></div>
    </div>
  </div>;
}

function InventoryView({ inventory, movements }) {
  const [category, setCategory] = useState("All items");
  const filtered = category === "All items" ? inventory : inventory.filter((item) => item.category === category);
  return <div className="space-y-5">
    <div className="flex flex-wrap gap-2">{["All items", "Raw material", "Packaging", "Finished goods"].map((item) => <button key={item} onClick={() => setCategory(item)} className={`rounded-full px-3 py-1.5 text-[10px] font-semibold ${category === item ? "bg-olive text-white" : "border border-line bg-white text-[#74766c]"}`}>{item}</button>)}</div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{filtered.map((item) => <div key={item.item_code} className="rounded-xl border border-line bg-white p-5 shadow-card"><div className="flex items-start justify-between"><div><div className="text-[10px] text-[#93948a]">{item.item_code}</div><div className="mt-1 font-display text-[14px] font-bold">{item.item_name}</div></div><span className="rounded-md bg-[#f2f1ec] p-2 text-olive"><Boxes size={15} /></span></div><div className="mt-5 flex items-end justify-between"><div className="font-display text-[25px] font-bold">{fmt(item.balance)}<span className="ml-1 text-[11px] font-medium text-[#909187]">{item.unit}</span></div><span className="text-[9px] text-[#96978d]">{item.category}</span></div></div>)}</div>
    <div className="rounded-xl border border-line bg-white shadow-card"><div className="border-b border-[#efeee8] px-5 py-4"><div className="font-display text-[13px] font-bold">Stock movement ledger</div><div className="mt-1 text-[10px] text-[#999a90]">Append-only records with a source and reference on every line.</div></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left"><thead><tr className="bg-[#fbfaf7] text-[9px] uppercase tracking-[.1em] text-[#9b9c92]">{["Time", "Item", "Movement", "Quantity", "Source", "Reference", "Actor"].map((x) => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{movements.map((row) => <tr key={row.id} className="border-t border-[#f0efe9] text-[9px]"><td className="px-4 py-3 text-[#8a8c82]">{row.created_at.slice(0, 16).replace("T", " ")}</td><td className="px-4 py-3 font-semibold">{row.item_name}</td><td className="px-4 py-3">{row.movement_type.replaceAll("_", " ")}</td><td className={`px-4 py-3 font-semibold ${Number(row.quantity) < 0 ? "text-[#a16e58]" : "text-olive"}`}>{Number(row.quantity) > 0 ? "+" : ""}{fmt(row.quantity)} {row.unit}</td><td className="px-4 py-3">{row.source_type}</td><td className="max-w-40 truncate px-4 py-3 font-mono text-[8px] text-[#888a81]">{row.source_id}</td><td className="px-4 py-3 text-[#898b82]">{row.actor}</td></tr>)}</tbody></table></div></div>
  </div>;
}

function CustomersView({ customers, products, bom, user, busy, onSaveProduct, onSaveBom }) {
  const product = products[0];
  const [productForm, setProductForm] = useState(() => product || {});
  const [bomForm, setBomForm] = useState(() => bom.map((line) => ({ ...line })));
  const editable = can(user, ["Admin", "Owner"]);
  const updateProductField = (key) => (event) => setProductForm((current) => ({ ...current, [key]: event.target.value }));
  const updateBomField = (itemCode, key) => (event) => setBomForm((current) =>
    current.map((line) => line.item_code === itemCode ? { ...line, [key]: event.target.value } : line));

  return <div className="space-y-5">
    <section className="rounded-xl border border-line bg-white shadow-card"><div className="border-b border-[#efeee8] px-5 py-4"><div className="font-display text-[13px] font-bold">Customer master</div><div className="mt-1 text-[10px] text-[#999a90]">Fictional benchmark customers · state code controls GST treatment.</div></div><div className="grid gap-3 p-4 md:grid-cols-2">{customers.map((customer) => <div key={customer.id} className="flex items-start gap-3 rounded-lg border border-[#efeee8] p-4"><div className="grid h-9 w-9 place-items-center rounded-lg bg-[#eff0e9] text-olive"><Users size={15} /></div><div className="min-w-0 flex-1"><div className="text-[12px] font-semibold">{customer.name}</div><div className="mt-1 text-[10px] text-[#898b82]">{customer.customer_type} · {customer.state}</div><div className="mt-2 text-[9px] text-[#9b9c92]">{customer.address}</div></div><span className="rounded-full bg-[#f4f2ec] px-2 py-1 text-[9px]">State {customer.state_code}</span></div>)}</div></section>
    <section className="rounded-xl border border-line bg-white shadow-card">
      <div className="border-b border-[#efeee8] px-5 py-4"><div className="font-display text-[13px] font-bold">Product & bill of materials</div><div className="mt-1 text-[10px] text-[#999a90]">Product tax settings and planned material consumption for Murukku 200 g.</div></div>
      {product && <div className="grid gap-5 p-5 lg:grid-cols-[.8fr_1.2fr]">
        <form className="space-y-3 rounded-lg bg-[#f6f5ef] p-4" onSubmit={(event) => { event.preventDefault(); onSaveProduct(product.id, { ...productForm, gst_rate: String(productForm.gst_rate) }); }}>
          <div className="mb-1 text-[10px] font-semibold text-[#73766b]">SELLABLE PRODUCT</div>
          {[["Product name", "name"], ["SKU", "sku"], ["HSN", "hsn"], ["GST rate (%)", "gst_rate"]].map(([label, key]) => <label key={key} className="block text-[9px] font-semibold text-[#77796f]">{label}<input required min={key === "gst_rate" ? 0 : undefined} max={key === "gst_rate" ? 100 : undefined} step={key === "gst_rate" ? "0.01" : undefined} type={key === "gst_rate" ? "number" : "text"} value={productForm[key] ?? ""} onChange={updateProductField(key)} disabled={!editable} className="mt-1 w-full rounded-md border border-[#e7e5dc] bg-white px-2.5 py-2 text-[10px] font-normal text-ink disabled:bg-[#f1f0eb]" /></label>)}
          {editable && <button disabled={busy} className="w-full rounded-md bg-olive px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-50">Save product</button>}
        </form>
        <form onSubmit={(event) => { event.preventDefault(); onSaveBom(product.id, bomForm.map(({ ingredient, item_code, quantity_per_packet, unit }) => ({ ingredient, item_code, quantity_per_packet: String(quantity_per_packet), unit }))); }}>
          <div className="mb-2 text-[10px] text-[#898b82]">Enter standard consumption per sellable packet. Inventory item codes and units stay fixed.</div>
          <div className="overflow-x-auto"><table className="w-full min-w-[480px] text-left"><thead><tr className="text-[9px] uppercase tracking-[.1em] text-[#9b9c92]"><th className="py-2">Ingredient</th><th className="py-2">Per packet</th><th className="py-2">Unit</th><th className="py-2">Item code</th></tr></thead><tbody>{bomForm.map((line) => <tr key={line.item_code} className="border-t border-[#f0efe9] text-[10px]"><td className="py-2 pr-2"><input required value={line.ingredient} onChange={updateBomField(line.item_code, "ingredient")} disabled={!editable} className="w-full rounded border border-[#e7e5dc] px-2 py-1.5 disabled:border-transparent disabled:bg-transparent" /></td><td className="py-2 pr-2"><input required type="number" min="0.001" step="0.001" value={line.quantity_per_packet} onChange={updateBomField(line.item_code, "quantity_per_packet")} disabled={!editable} className="w-24 rounded border border-[#e7e5dc] px-2 py-1.5 disabled:border-transparent disabled:bg-transparent" /></td><td className="py-2">{line.unit}</td><td className="py-2 font-mono text-[9px] text-[#888a81]">{line.item_code}</td></tr>)}</tbody></table></div>
          {editable && <button disabled={busy} className="mt-3 rounded-md bg-olive px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-50">Save bill of materials</button>}
        </form>
      </div>}
    </section>
  </div>;
}

function ReportsView({ invoices, user, onExport, onInvoice, onPayment, onCancel }) {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const monthlyInvoices = invoices.filter((row) => row.created_at?.slice(0, 7) === month);
  const postedInvoices = monthlyInvoices.filter((row) => row.status === "posted");
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white p-4 shadow-card">
      <div><div className="font-display text-[13px] font-bold">Monthly sales & GST</div><div className="mt-1 text-[10px] text-[#999a90]">Invoice totals include posted invoices for the selected month.</div></div>
      <label className="flex items-center gap-2 text-[10px] font-semibold text-[#66695f]">Report month<input required aria-label="Report month" type="month" value={month} onChange={(event) => setMonth(event.target.value)} className="rounded-md border border-[#e7e5dc] bg-[#fcfbf8] px-2.5 py-2 text-[11px]" /></label>
    </div>
    <div className="grid gap-3 sm:grid-cols-3">
      <Metric label="Taxable turnover" value={rupees(postedInvoices.reduce((sum, row) => sum + Number(row.taxable_amount), 0))} icon={BadgeIndianRupee} foot={`Posted invoices · ${month}`} color="olive" />
      <Metric label="GST collected" value={rupees(postedInvoices.reduce((sum, row) => sum + Number(row.cgst) + Number(row.sgst) + Number(row.igst), 0))} icon={FileText} foot={`All tax components · ${month}`} color="gold" />
      <Metric label="Open balance" value={rupees(postedInvoices.reduce((sum, row) => sum + Number(row.total) - Number(row.paid), 0))} icon={ArrowUpRight} foot={`Posted receivables · ${month}`} color="slate" />
    </div>
    <section className="rounded-xl border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#efeee8] px-5 py-4">
        <div><div className="font-display text-[13px] font-bold">Tax invoices & receivables</div><div className="mt-1 text-[10px] text-[#999a90]">Tax split follows place of supply. Posted invoices are never deleted.</div></div>
        <div className="flex gap-2"><button onClick={() => onExport("sales", "csv", month)} className="rounded-md border border-line px-2.5 py-1.5 text-[9px] font-semibold text-[#66695f]">Sales CSV</button><button onClick={() => onExport("gst", "xlsx", month)} className="rounded-md border border-line px-2.5 py-1.5 text-[9px] font-semibold text-[#66695f]">GST Excel</button></div>
      </div>
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left">
        <thead><tr className="bg-[#fbfaf7] text-[9px] uppercase tracking-[.1em] text-[#9b9c92]">{["Invoice", "Customer", "Taxable", "CGST", "SGST", "IGST", "Total", "Due", "Status", "Actions"].map((x) => <th key={x} className="px-3 py-3">{x}</th>)}</tr></thead>
        <tbody>{monthlyInvoices.length ? monthlyInvoices.map((row) => <tr key={row.id} className="border-t border-[#f0efe9] text-[9px]">
          <td className="px-3 py-4 font-semibold">{row.invoice_number}</td><td className="px-3 py-4"><div className="font-medium">{row.customer_name}</div><div className="mt-1 text-[#96978d]">{row.customer_state}</div></td><td className="px-3 py-4">{rupees(row.taxable_amount)}</td><td className="px-3 py-4">{rupees(row.cgst)}</td><td className="px-3 py-4">{rupees(row.sgst)}</td><td className="px-3 py-4">{rupees(row.igst)}</td><td className="px-3 py-4 font-semibold">{rupees(row.total)}</td><td className="px-3 py-4 font-semibold text-[#9b7255]">{row.status === "posted" ? rupees(Number(row.total) - Number(row.paid)) : "—"}</td><td className="px-3 py-4"><Status status={row.status} /></td>
          <td className="px-3 py-4"><div className="flex gap-2"><button title="Download invoice PDF" onClick={() => onInvoice(row.id)} className="text-olive"><Download size={13} /></button>{row.status === "posted" && can(user, ["Admin", "Owner"]) && Number(row.total) > Number(row.paid) && <button title="Record payment" onClick={() => onPayment(row)} className="text-olive"><Plus size={14} /></button>}{row.status === "posted" && Number(row.paid) === 0 && can(user, ["Admin", "Owner"]) && <button title="Cancel invoice and issue credit note" onClick={() => onCancel(row)} className="text-[#a16e58]"><X size={13} /></button>}</div></td>
        </tr>) : <tr><td colSpan="10" className="p-8 text-center text-[11px] text-[#898b82]">No invoices for {month}.</td></tr>}</tbody>
      </table></div>
    </section>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[["GST summary", "gst"], ["Purchase report", "purchases"], ["Production report", "production"], ["Stock ledger", "ledger"]].map(([label, slug]) => <div key={slug} className="flex items-center justify-between rounded-xl border border-line bg-white p-4 shadow-card"><div><div className="text-[11px] font-semibold">{label}</div><div className="mt-1 text-[9px] text-[#96978e]">Monthly · CSV or Excel</div></div><div className="flex gap-2"><button onClick={() => onExport(slug, "csv", month)} className="rounded border border-line px-2 py-1 text-[9px]">CSV</button><button onClick={() => onExport(slug, "xlsx", month)} className="rounded border border-line px-2 py-1 text-[9px]">XLSX</button></div></div>)}</div>
  </div>;
}

function WorkflowModal({ modal, selected, customers, busy, onClose, onSubmit }) {
  const [form, setForm] = useState({});
  const change = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  const field = (label, key, initial, type = "number", step = "1") => <label key={key} className="block"><span className="mb-1.5 block text-[10px] font-semibold text-[#66695e]">{label}</span><input required type={type} step={step} min={type === "number" ? "0" : undefined} value={form[key] ?? initial} onChange={change(key)} className="w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[11px] outline-none focus:border-olive" /></label>;
  const title = { order: "Create sales order", production: "Record production run", dispatch: "Dispatch approved order", payment: "Record customer payment", purchase: "Record inventory purchase", customer: "Add customer", cancel: "Cancel invoice & issue credit note" }[modal];
  const submit = (event) => {
    event.preventDefault();
    if (modal === "order") onSubmit("/api/orders", { customer_id: form.customer_id || customers[0]?.id, quantity: Number(form.quantity), unit_price: Number(form.unit_price) }, "Order submitted for admin review.");
    if (modal === "production") onSubmit("/api/production", { expected_packets: Number(form.expected_packets ?? 200), actual_good_packets: Number(form.actual_good_packets), flour_kg: Number(form.flour_kg), oil_litres: Number(form.oil_litres), spice_kg: Number(form.spice_kg), damaged_pouches: Number(form.damaged_pouches ?? 0), cartons_used: Number(form.cartons_used ?? 0) }, "Production and ledger entries posted together.");
    if (modal === "dispatch") onSubmit(`/api/orders/${selected.id}/dispatch`, { quantity: Number(form.quantity ?? selected.quantity) }, "Dispatch posted and tax invoice created.");
    if (modal === "payment") onSubmit(`/api/invoices/${selected.id}/payments`, { amount: Number(form.amount), method: form.method || "Bank transfer", reference: form.reference || "" }, "Payment recorded against invoice.");
    if (modal === "purchase") onSubmit("/api/purchases", { item_code: form.item_code || "RM-FLOUR", quantity: Number(form.quantity), unit_price: Number(form.unit_price), supplier: form.supplier, reference: form.reference || "", purchase_date: form.purchase_date || "2026-11-18" }, "Purchase and stock receipt posted together.");
    if (modal === "customer") onSubmit("/api/customers", { name: form.name, customer_type: form.customer_type || "Retailer", address: form.address, state: form.state || "Tamil Nadu", state_code: form.state_code || "33", gstin: form.gstin || "", phone: form.phone || "" }, "Customer added to the master.");
    if (modal === "cancel") onSubmit(`/api/invoices/${selected.id}/cancel`, { reason: form.reason }, "Invoice cancelled and credit note issued.");
  };
  const fields = {
    order: <><label className="block"><span className="mb-1.5 block text-[10px] font-semibold text-[#66695e]">Customer</span><select value={form.customer_id || customers[0]?.id || ""} onChange={change("customer_id")} className="w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[11px]">{customers.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.state}</option>)}</select></label>{field("Quantity (packets)", "quantity", "50")}{field("Selling price (₹ / packet)", "unit_price", "50", "number", "0.01")}</>,
    production: <>{field("Expected packets", "expected_packets", "200")}{field("Actual good output (packets)", "actual_good_packets", "188")}{field("Flour used (kg)", "flour_kg", "40", "number", "0.001")}{field("Oil used (litres)", "oil_litres", "10.5", "number", "0.001")}{field("Spice mix used (kg)", "spice_kg", "1.2", "number", "0.001")}{field("Damaged pouches", "damaged_pouches", "6")}{field("Cartons used", "cartons_used", "9")}</>,
    dispatch: <><div className="rounded-lg bg-[#f5f4ef] p-3 text-[10px] leading-5 text-[#77796f]">{selected?.customer_name} · {selected?.customer_state}<br />Order quantity {selected?.quantity} · Tax treatment {selected?.tax_treatment}</div>{field("Dispatch quantity (packets)", "quantity", String(selected?.quantity || ""))}</>,
    payment: <><div className="rounded-lg bg-[#f5f4ef] p-3 text-[10px] leading-5 text-[#77796f]">{selected?.invoice_number} · {selected?.customer_name}<br />Outstanding {rupees(Number(selected?.total) - Number(selected?.paid))}</div>{field("Payment amount (₹)", "amount", "", "number", "0.01")}<label className="block"><span className="mb-1.5 block text-[10px] font-semibold text-[#66695e]">Method</span><select value={form.method || "Bank transfer"} onChange={change("method")} className="w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[11px]"><option>Bank transfer</option><option>UPI</option><option>Cash</option><option>Cheque</option></select></label>{field("Reference (optional)", "reference", "", "text")}</>,
    purchase: <><label className="block"><span className="mb-1.5 block text-[10px] font-semibold text-[#66695e]">Inventory item</span><select value={form.item_code || "RM-FLOUR"} onChange={change("item_code")} className="w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[11px]"><option value="RM-FLOUR">Flour · kg</option><option value="RM-OIL">Oil · litre</option><option value="RM-SPICE">Spice mix · kg</option><option value="PK-POUCH">Pouches · piece</option><option value="PK-CARTON">Cartons · piece</option></select></label>{field("Quantity", "quantity", "", "number", "0.001")}{field("Unit cost (₹)", "unit_price", "", "number", "0.01")}{field("Supplier", "supplier", "", "text")}{field("Bill reference (optional)", "reference", "", "text")}{field("Purchase date", "purchase_date", "2026-11-18", "date")}</>,
    customer: <>{field("Customer name", "name", "", "text")}{field("Customer type", "customer_type", "Retailer", "text")}{field("Address", "address", "", "text")}<label className="block"><span className="mb-1.5 block text-[10px] font-semibold text-[#66695e]">State</span><select value={form.state || "Tamil Nadu"} onChange={(event) => setForm((value) => ({ ...value, state: event.target.value, state_code: event.target.value === "Tamil Nadu" ? "33" : "29" }))} className="w-full rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[11px]"><option>Tamil Nadu</option><option>Karnataka</option></select></label>{field("GSTIN (optional)", "gstin", "", "text")}{field("Phone (optional)", "phone", "", "text")}</>,
    cancel: <><div className="rounded-lg bg-[#f7f1eb] p-3 text-[10px] leading-5 text-[#806b5b]">{selected?.invoice_number} · {selected?.customer_name}<br />Cancelling preserves this invoice and creates a credit note reference.</div><label className="block"><span className="mb-1.5 block text-[10px] font-semibold text-[#66695e]">Reason</span><textarea required minLength={5} maxLength={500} value={form.reason || ""} onChange={(event) => setForm((value) => ({ ...value, reason: event.target.value }))} rows={3} className="w-full resize-none rounded-lg border border-[#e7e5dc] bg-[#fcfbf8] px-3 py-2.5 text-[11px] outline-none focus:border-olive" /></label></>,
  }[modal];
  return <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#20231f]/35 p-4" onClick={onClose}><div className="my-auto w-full max-w-[460px] rounded-xl border border-line bg-white shadow-xl" onClick={(event) => event.stopPropagation()}><div className="flex items-center justify-between border-b border-[#efeee8] px-5 py-4"><div className="font-display text-[14px] font-bold">{title}</div><button aria-label="Close" onClick={onClose} className="rounded p-1 text-[#91938a] hover:bg-[#f3f2ed]"><X size={16} /></button></div><form onSubmit={submit}><div className="grid max-h-[70vh] gap-3 overflow-y-auto p-5">{fields}</div><div className="flex justify-end gap-2 border-t border-[#efeee8] px-5 py-4"><button type="button" onClick={onClose} className="rounded-lg border border-line px-3 py-2 text-[10px] font-semibold text-[#65685e]">Cancel</button><button disabled={busy} className="rounded-lg bg-olive px-4 py-2 text-[10px] font-semibold text-white disabled:opacity-60">{busy ? "Saving..." : modal === "dispatch" ? "Dispatch & invoice" : "Save transaction"}</button></div></form></div></div>;
}

function Toast({ kind, message, onClose }) {
  return <div className={`mb-4 flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-[11px] ${kind === "error" ? "border-[#ead5ce] bg-[#fbf1ed] text-[#9c624e]" : "border-[#dce4d4] bg-[#f0f4ed] text-[#62764d]"}`}><span className="flex items-center gap-2">{kind === "error" ? <CircleAlert size={14} /> : <Check size={14} />}{message}</span>{onClose && <button onClick={onClose}><X size={14} /></button>}</div>;
}
function Button({ children, onClick }) { return <button onClick={onClick} className="flex items-center gap-2 rounded-lg bg-olive px-3 py-2 text-[10px] font-semibold text-white shadow-sm transition hover:bg-[#56613f]">{children}</button>; }
function Loading() { return <div className="rounded-xl border border-line bg-white p-10 text-center text-[12px] text-[#8d8f85]">Connecting to local demo data…</div>; }

export default App;
