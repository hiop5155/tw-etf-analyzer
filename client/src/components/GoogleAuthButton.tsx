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
              text: "signin",
              locale: "zh_TW",
              width: 130,
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

  const [imgError, setImgError] = useState(false);

  if (isLoggedIn && user) {
    return (
      <div className="relative">
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors text-xs"
        >
          {user.avatar && !imgError ? (
            <img
              src={user.avatar}
              alt={user.name}
              referrerPolicy="no-referrer"
              onError={() => setImgError(true)}
              className="w-5 h-5 rounded-full object-cover"
            />
          ) : (
            <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-[10px] text-white font-bold">
              {user.name.charAt(0).toUpperCase()}
            </div>
          )}
          <span className="font-medium text-slate-200 hidden md:inline max-w-[100px] truncate">
            {user.name}
          </span>

          {/* 雲端自動同步指示燈：恆亮綠色，全自動儲存 */}
          <span className="w-2 h-2 rounded-full bg-emerald-400" title="雲端設定已連線，全自動儲存中" />
        </button>

        {showDropdown && (
          <div className="absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-800 rounded-xl shadow-xl p-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
            <div className="px-3 py-2.5 border-b border-slate-800/80 mb-1 flex items-center gap-2.5">
              {user.avatar && !imgError ? (
                <img
                  src={user.avatar}
                  alt={user.name}
                  referrerPolicy="no-referrer"
                  onError={() => setImgError(true)}
                  className="w-8 h-8 rounded-full object-cover shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-xs text-white font-bold shrink-0">
                  {user.name.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-white truncate">{user.name}</div>
                <div className="text-[11px] text-slate-400 truncate">{user.email}</div>
                <div className="flex items-center gap-1.5 mt-1 text-[10px] text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>雲端自動同步中</span>
                </div>
              </div>
            </div>

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
    <div className="flex items-center gap-2 shrink-0">
      <div ref={buttonDivRef} className="h-8 flex items-center overflow-hidden rounded-full shrink-0" />
      {!isGsiLoaded && (
        <button
          onClick={() => {
            alert("正在載入 Google 登入服務，請稍候...");
          }}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/60 text-slate-300 border border-slate-700/60 hover:bg-slate-800 flex items-center gap-1.5 shrink-0 whitespace-nowrap"
        >
          <Cloud className="w-3.5 h-3.5 text-slate-400" />
          <span>登入</span>
        </button>
      )}
    </div>
  );
};
