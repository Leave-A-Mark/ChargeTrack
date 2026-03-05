import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Battery, Plus, Trash2, Users, Cpu, LogOut, Pencil, Copy, Check, Send
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

interface BotUser {
  id: number;
  name: string;
  equipment_id: string;
  secret_code: string;
  telegram_id: number | null;
}

const API_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000/api`;

const Dashboard = () => {
  const navigate = useNavigate();
  const [users, setUsers] = useState<BotUser[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<BotUser | null>(null);
  const [form, setForm] = useState({ name: "", equipment_id: "" });
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [instructionOpen, setInstructionOpen] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_URL}/subscribers`);
      const data = await res.json();
      setUsers(data);
    } catch (error) {
      toast.error("Помилка при завантаженні користувачів");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("auth");
    navigate("/");
  };

  const openAdd = () => {
    setEditingUser(null);
    setForm({ name: "", equipment_id: "" });
    setDialogOpen(true);
  };

  const openEdit = (user: BotUser) => {
    setEditingUser(user);
    setForm({
      name: user.name,
      equipment_id: user.equipment_id,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name || !form.equipment_id) {
      toast.error("Заповніть усі поля");
      return;
    }

    try {
      if (editingUser) {
        const res = await fetch(`${API_URL}/subscribers/${editingUser.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        if (res.ok) {
          toast.success("Користувача оновлено");
          fetchUsers();
        }
      } else {
        const res = await fetch(`${API_URL}/subscribers`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        if (res.ok) {
          toast.success("Користувача додано");
          fetchUsers();
        }
      }
      setDialogOpen(false);
    } catch (error) {
      toast.error("Помилка при збереженні");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      const res = await fetch(`${API_URL}/subscribers/${id}`, { method: "DELETE" });
      if (res.ok) {
        toast.success("Користувача видалено");
        fetchUsers();
      }
    } catch (error) {
      toast.error("Помилка при видаленні");
    }
  };

  const copyToClipboard = (code: string, id: number) => {
    // Works on both localhost and network IP (no HTTPS required)
    const fallbackCopy = (text: string) => {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    };

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(code).catch(() => fallbackCopy(code));
    } else {
      fallbackCopy(code);
    }

    setCopiedId(id);
    toast.success("Код скопійовано");
    setInstructionOpen(true);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const copyBotLink = () => {
    const link = "https://t.me/chargetrack_bot";
    const fallbackCopy = (text: string) => {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(link).catch(() => fallbackCopy(link));
    } else {
      fallbackCopy(link);
    }
    toast.success("Посилання на бота скопійовано");
  };

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-primary/20 p-2 rounded-lg">
              <Battery className="w-6 h-6 text-primary animate-pulse" />
            </div>
            <span className="font-bold text-xl tracking-tight text-foreground">ChargeTrack</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={copyBotLink} className="hidden sm:flex items-center gap-2 border-primary/20 hover:bg-primary/5 text-primary">
              <Send className="w-4 h-4" />
              @chargetrack_bot
            </Button>
            <Button variant="ghost" size="sm" onClick={handleLogout} className="text-muted-foreground hover:text-foreground">
              <LogOut className="w-4 h-4 mr-2" />
              Вийти
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
          <StatCard icon={<Users className="w-5 h-5 text-primary" />} label="Користувачів" value={users.length} />
          <StatCard icon={<Cpu className="w-5 h-5 text-primary" />} label="Обладнання" value={new Set(users.map((u) => u.equipment_id)).size} />
        </div>

        {/* Title + Add */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-foreground">Користувачі бота</h2>
            <p className="text-sm text-muted-foreground">Управління підписниками Telegram бота</p>
          </div>
          <Button onClick={openAdd} className="shadow-lg shadow-primary/20 transition-all hover:scale-105 active:scale-95">
            <Plus className="w-5 h-5 mr-2" />
            Додати
          </Button>
        </div>

        {/* Table */}
        <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-xl shadow-black/5">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  {["Ім'я", "ID обладнання", "Секретний код", "Статус ТГ", ""].map((h, i) => (
                    <th key={i} className={`text-xs font-bold uppercase tracking-wider text-muted-foreground px-6 py-4 ${i === 4 ? "text-right" : "text-left"}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr><td colSpan={5} className="px-6 py-12 text-center text-muted-foreground animate-pulse">Завантаження...</td></tr>
                ) : users.map((user) => (
                  <tr key={user.id} className="hover:bg-muted/20 transition-colors group">
                    <td className="px-6 py-4 text-sm font-semibold text-foreground">{user.name}</td>
                    <td className="px-6 py-4">
                      <span className="text-xs font-mono bg-primary/10 text-primary px-3 py-1 rounded-full">
                        {user.equipment_id}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-sm">
                      <div className="flex items-center gap-2">
                        <span className="bg-muted px-2 py-0.5 rounded border border-border/50">{user.secret_code}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => copyToClipboard(user.secret_code, user.id)}
                        >
                          {copiedId === user.id ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                        </Button>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {user.telegram_id ? (
                        <span className="flex items-center gap-1.5 text-xs font-medium text-green-500 bg-green-500/10 px-2.5 py-1 rounded-full w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                          Активний
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-muted-foreground bg-muted px-2.5 py-1 rounded-full w-fit">
                          Очікує
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(user)} className="text-muted-foreground hover:text-primary transition-colors">
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(user.id)} className="text-muted-foreground hover:text-destructive transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {!loading && users.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-16 text-center text-muted-foreground text-sm flex flex-col items-center gap-2">
                      <Users className="w-10 h-10 opacity-20" />
                      Немає активних підписок
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md border-border bg-card shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">{editingUser ? "Редагувати користувача" : "Новий користувач"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 mt-4">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-foreground/80">Ім'я користувача</label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Іван Іванов"
                className="bg-muted/50 border-border focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold text-foreground/80">ID обладнання</label>
              <Input
                value={form.equipment_id}
                onChange={(e) => setForm({ ...form, equipment_id: e.target.value })}
                placeholder="EQUIP-001"
                className="bg-muted/50 border-border focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <Button onClick={handleSave} className="w-full h-11 text-base font-semibold shadow-lg shadow-primary/20">
              {editingUser ? "Зберегти зміни" : "Створити підписку"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Instruction Dialog */}
      <Dialog open={instructionOpen} onOpenChange={setInstructionOpen}>
        <DialogContent className="sm:max-w-md border-border bg-card shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold flex items-center gap-2">
              <Send className="w-5 h-5 text-primary" />
              Як активувати відстеження?
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="bg-primary/5 p-4 rounded-xl border border-primary/10 space-y-3">
              <p className="text-sm leading-relaxed">
                Код успішно скопійовано! Тепер виконайте ці прості кроки:
              </p>
              <ol className="text-sm space-y-2 list-decimal list-inside font-medium italic">
                <li>Перейдіть у Telegram-бот <span className="text-primary">@chargetrack_bot</span></li>
                <li>Надішліть боту скопійований код</li>
                <li>Отримуйте автоматичні сповіщення про стан акумуляторів!</li>
              </ol>
            </div>
            <Button onClick={() => setInstructionOpen(false)} className="w-full h-11 text-base font-semibold shadow-lg shadow-primary/20">
              Зрозуміло
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const StatCard = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) => (
  <div className="bg-card border border-border rounded-2xl p-5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
      {icon}
    </div>
    <div>
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold text-foreground">{value}</p>
    </div>
  </div>
);

export default Dashboard;
