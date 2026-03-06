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

interface Device {
  id: number;
  equipment_id: string;
  name: string;
  v1_offset: number;
  v2_offset: number;
  v3_offset: number;
  v4_offset: number;
  v5_offset: number;
  v6_offset: number;
  v7_offset: number;
  active_sensors: string;
}

const API_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000/api`;

const Dashboard = () => {
  const navigate = useNavigate();
  const [users, setUsers] = useState<BotUser[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<BotUser | null>(null);
  const [form, setForm] = useState({ name: "", equipment_ids: [""] });
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [instructionOpen, setInstructionOpen] = useState(false);

  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceDialogOpen, setDeviceDialogOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [deviceForm, setDeviceForm] = useState<Partial<Device>>({});

  const [confirmDelete, setConfirmDelete] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: "",
    description: "",
    onConfirm: () => { },
  });

  useEffect(() => {
    fetchUsers();
    fetchDevices();
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

  const fetchDevices = async () => {
    try {
      const res = await fetch(`${API_URL}/devices`);
      const data = await res.json();
      setDevices(data);
    } catch (error) {
      toast.error("Помилка при завантаженні пристроїв");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("auth");
    navigate("/");
  };

  const openAdd = () => {
    setEditingUser(null);
    setForm({ name: "", equipment_ids: [""] });
    setDialogOpen(true);
  };

  const openEdit = (user: BotUser) => {
    setEditingUser(user);
    const ids = user.equipment_id.split(",").map(id => id.trim()).filter(Boolean);
    setForm({
      name: user.name,
      equipment_ids: ids.length > 0 ? ids : [""],
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name || form.equipment_ids.some(id => !id.trim())) {
      toast.error("Заповніть усі поля");
      return;
    }

    const payload = {
      name: form.name,
      equipment_id: form.equipment_ids.join(","),
    };

    try {
      if (editingUser) {
        const res = await fetch(`${API_URL}/subscribers/${editingUser.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          toast.success("Користувача оновлено");
          fetchUsers();
        }
      } else {
        const res = await fetch(`${API_URL}/subscribers`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
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

  const handleDelete = (id: number) => {
    setConfirmDelete({
      isOpen: true,
      title: "Видалити підписку?",
      description: "Ця дія безповоротна. Користувач більше не зможе отримувати оновлення через бот.",
      onConfirm: async () => {
        try {
          const res = await fetch(`${API_URL}/subscribers/${id}`, { method: "DELETE" });
          if (res.ok) {
            toast.success("Користувача видалено");
            fetchUsers();
          }
        } catch (error) {
          toast.error("Помилка при видаленні");
        }
        setConfirmDelete(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const openEditDevice = (device: Device) => {
    setEditingDevice(device);
    setDeviceForm(device);
    setDeviceDialogOpen(true);
  };

  const handleDeviceSave = async () => {
    if (!editingDevice) return;
    try {
      const res = await fetch(`${API_URL}/devices/${editingDevice.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(deviceForm),
      });
      if (res.ok) {
        toast.success("Налаштування пристрою збережено");
        fetchDevices();
        setDeviceDialogOpen(false);
      }
    } catch (error) {
      toast.error("Помилка при збереженні пристрою");
    }
  };

  const handleDeleteDevice = (id: number) => {
    setConfirmDelete({
      isOpen: true,
      title: "Видалити пристрій?",
      description: "Це видалить пристрій та всю історію його показників з бази даних. Цю дію неможливо скасувати.",
      onConfirm: async () => {
        try {
          const res = await fetch(`${API_URL}/devices/${id}`, { method: "DELETE" });
          if (res.ok) {
            toast.success("Пристрій видалено");
            fetchDevices();
          }
        } catch (error) {
          toast.error("Помилка при видаленні пристрою");
        }
        setConfirmDelete(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const removeIdFromUser = (user: BotUser, idToRemove: string) => {
    setConfirmDelete({
      isOpen: true,
      title: "Припинити відстеження?",
      description: `Ви впевнені, що хочете видалити ${idToRemove} зі списку підписок ${user.name}?`,
      onConfirm: async () => {
        const ids = user.equipment_id.split(",").map(id => id.trim()).filter(id => id !== idToRemove);
        const newEquipmentId = ids.join(",");

        try {
          const res = await fetch(`${API_URL}/subscribers/${user.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...user, equipment_id: newEquipmentId }),
          });
          if (res.ok) {
            toast.success(`ID ${idToRemove} видалено зі списку`);
            fetchUsers();
          }
        } catch (error) {
          toast.error("Помилка при оновленні списку ID");
        }
        setConfirmDelete(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const toggleSensor = (sensor: string) => {
    const current = deviceForm.active_sensors || "";
    const sensors = current.split(",").filter(Boolean);
    let next: string[];
    if (sensors.includes(sensor)) {
      next = sensors.filter(s => s !== sensor);
    } else {
      next = [...sensors, sensor].sort();
    }
    setDeviceForm({ ...deviceForm, active_sensors: next.join(",") });
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
          <StatCard icon={<Cpu className="w-5 h-5 text-primary" />} label="Обладнання" value={new Set(users.flatMap((u) => u.equipment_id.split(",").map(id => id.trim()))).size} />
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
                      <div className="flex flex-wrap gap-1">
                        {user.equipment_id.split(",").map((id, idx) => (
                          <span key={idx} className="group/badge relative text-[10px] font-mono bg-primary/10 text-primary px-2 py-0.5 pr-5 rounded-full uppercase font-bold">
                            {id.trim()}
                            <button
                              onClick={() => removeIdFromUser(user, id.trim())}
                              className="absolute right-1 top-1/2 -translate-y-1/2 w-3.5 h-3.5 flex items-center justify-center rounded-full hover:bg-primary/20 transition-colors"
                            >
                              <Plus className="w-2.5 h-2.5 rotate-45" />
                            </button>
                          </span>
                        ))}
                      </div>
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
        {/* Title + Add Devices */}
        <div className="flex items-center justify-between mt-12 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-foreground">Обладнання</h2>
            <p className="text-sm text-muted-foreground">Керування підключеними пристроями та калібрування</p>
          </div>
        </div>

        {/* Devices Table */}
        <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-xl shadow-black/5 mb-20">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  {["Назва", "ID", "Датчики (активні)", ""].map((h, i) => (
                    <th key={i} className={`text-xs font-bold uppercase tracking-wider text-muted-foreground px-6 py-4 text-left`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {devices.map((device) => (
                  <tr key={device.id} className="hover:bg-muted/20 transition-colors group">
                    <td className="px-6 py-4 text-sm font-semibold text-foreground">{device.name}</td>
                    <td className="px-6 py-4 text-xs font-mono text-muted-foreground">{device.equipment_id}</td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {device.active_sensors.split(",").filter(Boolean).map(s => (
                          <span key={s} className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded uppercase font-bold">
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <Button variant="ghost" size="sm" onClick={() => openEditDevice(device)} className="text-muted-foreground hover:text-primary transition-colors">
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteDevice(device.id)} className="text-muted-foreground hover:text-destructive transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
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
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-semibold text-foreground/80">ID обладнання</label>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setForm({ ...form, equipment_ids: [...form.equipment_ids, ""] })}
                  className="h-7 text-xs text-primary hover:text-primary hover:bg-primary/10"
                >
                  <Plus className="w-3 h-3 mr-1" /> Додати ще
                </Button>
              </div>
              <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                {form.equipment_ids.map((id, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      value={id}
                      onChange={(e) => {
                        const newIds = [...form.equipment_ids];
                        newIds[index] = e.target.value;
                        setForm({ ...form, equipment_ids: newIds });
                      }}
                      placeholder="EQUIP-001"
                      className="bg-muted/50 border-border focus:ring-2 focus:ring-primary/20 transition-all flex-1"
                    />
                    {form.equipment_ids.length > 1 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          const newIds = form.equipment_ids.filter((_, i) => i !== index);
                          setForm({ ...form, equipment_ids: newIds });
                        }}
                        className="h-10 w-10 text-muted-foreground hover:text-destructive transition-colors shrink-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
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

      {/* Device Calibration Dialog */}
      <Dialog open={deviceDialogOpen} onOpenChange={setDeviceDialogOpen}>
        <DialogContent className="sm:max-w-lg border-border bg-card shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">Налаштування пристрою: {editingDevice?.equipment_id}</DialogTitle>
          </DialogHeader>
          <div className="space-y-6 mt-4">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-foreground/80">Назва пристрою</label>
              <Input
                value={deviceForm.name || ""}
                onChange={(e) => setDeviceForm({ ...deviceForm, name: e.target.value })}
                placeholder="Назва"
                className="bg-muted/50"
              />
            </div>

            <div>
              <label className="text-sm font-semibold text-foreground/80 block mb-3">Корекція напруги (V)</label>
              <div className="grid grid-cols-2 gap-4">
                {["v1", "v2", "v3", "v4", "v5", "v6", "v7"].map(v => (
                  <div key={v} className="flex items-center gap-2">
                    <span className="text-xs font-bold w-6 uppercase text-muted-foreground">{v}:</span>
                    <Input
                      type="number"
                      step="0.01"
                      value={deviceForm[`${v}_offset` as keyof Device] || 0}
                      onChange={(e) => setDeviceForm({ ...deviceForm, [`${v}_offset`]: parseFloat(e.target.value) })}
                      className="h-8 text-xs bg-muted/30"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm font-semibold text-foreground/80 block mb-3">Активні датчики</label>
              <div className="flex flex-wrap gap-2">
                {["v1", "v2", "v3", "v4", "v5", "v6", "v7"].map(v => (
                  <Button
                    key={v}
                    variant={deviceForm.active_sensors?.includes(v) ? "default" : "outline"}
                    size="sm"
                    onClick={() => toggleSensor(v)}
                    className="h-8 px-3 text-xs uppercase font-bold"
                  >
                    {v}
                  </Button>
                ))}
              </div>
            </div>

            <Button onClick={handleDeviceSave} className="w-full h-11 text-base font-semibold shadow-lg shadow-primary/20">
              Зберегти налаштування
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmDelete.isOpen} onOpenChange={(open) => setConfirmDelete({ ...confirmDelete, isOpen: open })}>
        <DialogContent className="max-w-md bg-card/95 backdrop-blur-xl border-border shadow-2xl p-0 overflow-hidden">
          <div className="p-6">
            <DialogHeader className="mb-4">
              <DialogTitle className="text-xl font-bold text-foreground">
                {confirmDelete.title}
              </DialogTitle>
            </DialogHeader>
            <p className="text-muted-foreground mb-6">
              {confirmDelete.description}
            </p>
            <div className="flex gap-3">
              <Button
                variant="ghost"
                onClick={() => setConfirmDelete({ ...confirmDelete, isOpen: false })}
                className="flex-1 hover:bg-muted font-semibold"
              >
                Скасувати
              </Button>
              <Button
                variant="destructive"
                onClick={confirmDelete.onConfirm}
                className="flex-1 font-semibold shadow-lg shadow-destructive/20"
              >
                Видалити
              </Button>
            </div>
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
