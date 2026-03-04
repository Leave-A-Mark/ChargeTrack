import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Battery, Eye, EyeOff, Lock } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const API_URL = `http://${window.location.hostname}:8000/api`;

const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      toast.error("Введіть логін та пароль");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (res.ok && data.auth) {
        localStorage.setItem("auth", "true");
        navigate("/dashboard");
        toast.success("Ласкаво просимо!");
      } else {
        toast.error("Невірний логін або пароль");
      }
    } catch (error) {
      toast.error("Помилка підключення до сервера");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 opacity-20 pointer-events-none">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-primary rounded-full blur-[120px]" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-primary rounded-full blur-[120px]" />
      </div>

      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center gap-4 mb-10">
          <div className="bg-primary/10 p-4 rounded-2xl shadow-inner border border-primary/20">
            <img src="/logo.svg" alt="ChargeTrack Logo" className="w-12 h-12 animate-pulse" />
          </div>
          <div className="text-center">
            <h1 className="text-4xl font-extrabold text-foreground tracking-tighter">
              ChargeTrack
            </h1>
            <p className="text-muted-foreground font-medium">BMS Monitoring System</p>
          </div>
        </div>

        <div className="bg-card/50 backdrop-blur-xl border border-border rounded-3xl p-8 shadow-2xl shadow-black/10">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-foreground">Авторизація</h2>
            <p className="text-sm text-muted-foreground">Введіть дані адміністратора</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-foreground/80 ml-1">Логін</label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Manager ID"
                className="h-12 bg-muted/50 border-border focus:ring-2 focus:ring-primary/20 transition-all rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between items-center ml-1">
                <label className="text-sm font-semibold text-foreground/80">Пароль</label>
              </div>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-12 bg-muted/50 border-border focus:ring-2 focus:ring-primary/20 transition-all rounded-xl pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="w-full h-12 text-lg font-bold shadow-lg shadow-primary/20 rounded-xl mt-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-background/20 border-t-background rounded-full animate-spin" />
                  Вхід...
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  Увійти
                </div>
              )}
            </Button>
          </form>
        </div>

        <p className="text-center mt-8 text-xs text-muted-foreground">
          &copy; 2026 ChargeTrack. Усі права захищені.
        </p>
      </div>
    </div>
  );
};

export default Login;
