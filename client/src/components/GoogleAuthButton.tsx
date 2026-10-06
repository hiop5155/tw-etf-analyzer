import React, { useEffect, useRef, useState } from "react";
import { useApp } from "../context/AppContext";
import { Cloud, CloudCheck, RefreshCw, LogOut, User as UserIcon } from "lucide-react";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";


declare global {
  interface Window {
    google?: any;
  }
}

export const GoogleAuthButton: React.FC = () => {
  const { user, isLoggedIn, syncStatus, loginWithGoogle, logout, syncNow } = useApp();
  const [showDropdown, setShowDropdown] = useState(false);
  const buttonDivRef = useRef<HTMLDivElement>(null);
  const [isGsiLoaded, setIsGsiLoaded] = useState(false);

  useEffect(() => {
    const checkGsi = () => {
      if (window.google?.accounts?.id) {
        if (!GOOGLE_CLIENT_ID) {
          console.warn("VITE_GOOGLE_CLIENT_ID is not configured in environment");
          return;
        }
        setIsGsiLoaded(true);
        try {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: (response: { credential?: string }) => {
              if (response.credential) {
                loginWithGoogle(response.credential);
              }
            },
            auto_select: false,
          });

          if (!isLoggedIn && buttonDivRef.current) {
            window.google.accounts.id.renderButton(buttonDivRef.current, {
              theme: "filled_black",
              size: "medium",
              shape: "pill",
              text: "signin_with",
              locale: "zh_TW",
            });
          }
        } catch (e) {
          console.warn("Google GSI init failed:", e);
        }
      } else {
        setTimeout(checkGsi, 300);
      }
    };
    checkGsi();
  }, [isLoggedIn, loginWithGoogle]);

  if (isLoggedIn && user) {
    return (
      <div className="relative">
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors text-xs"
        >
          {user.avatar ? (
            <img src={user.avatar} alt={user.name} className="w-5 h-5 rounded-full object-cover" />
          ) : (
            <div className="w-5 h-5 rounded-full bg-indigo-600 flex items-center justify-center text-[10px] text-white font-bold">
              {user.name.charAt(0).toUpperCase()}
            </div>
          )}
          <span className="font-medium text-slate-200 hidden md:inline max-w-[100px] truncate">
            {user.name}
          </span>

          {/* 同步狀態指示 */}
          {syncStatus === "syncing" && (
            <span title="同步至 D1 資料庫中...">
              <RefreshCw className="w-3.5 h-3.5 text-amber-400 animate-spin" />
            </span>
          )}
          {syncStatus === "saved" && (
            <span className="w-2 h-2 rounded-full bg-emerald-400" title="已同步至 D1 資料庫" />
          )}
          {syncStatus === "error" && (
            <span className="w-2 h-2 rounded-full bg-rose-400" title="同步異常" />
          )}
        </button>

        {showDropdown && (
          <div className="absolute right-0 mt-2 w-52 bg-slate-900 border border-slate-800 rounded-xl shadow-xl p-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
            <div className="px-3 py-2 border-b border-slate-800/80 mb-1">
              <div className="text-xs font-semibold text-white truncate">{user.name}</div>
              <div className="text-[11px] text-slate-400 truncate">{user.email}</div>
              <div className="flex items-center gap-1.5 mt-2 text-[10px] text-emerald-400 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span>Cloudflare D1 雲端已連線</span>
              </div>
            </div>

            <button
              onClick={() => {
                syncNow();
                setShowDropdown(false);
              }}
              className="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-slate-800 flex items-center gap-2 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncStatus === "syncing" ? "animate-spin" : ""}`} />
              <span>立即同步設定</span>
            </button>

            <button
              onClick={() => {
                logout();
                setShowDropdown(false);
              }}
              className="w-full text-left px-3 py-2 rounded-lg text-xs text-rose-400 hover:bg-rose-500/10 flex items-center gap-2 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>登出 Google 帳號</span>
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div ref={buttonDivRef} className="h-8 flex items-center overflow-hidden rounded-full" />
      {!isGsiLoaded && (
        <button
          onClick={() => {
            alert("正在載入 Google 登入服務，請稍候...");
          }}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/60 text-slate-300 border border-slate-700/60 hover:bg-slate-800 flex items-center gap-1.5"
        >
          <Cloud className="w-3.5 h-3.5 text-slate-400" />
          <span>登入以同步</span>
        </button>
      )}
    </div>
  );
};
