import React from "react";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subValue?: string;
  subLabel?: string;
  icon?: LucideIcon;
  badge?: string;
  badgeColor?: "green" | "red" | "indigo" | "amber" | "slate" | "cyan";
  trend?: "up" | "down" | "neutral";
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subValue,
  subLabel,
  icon: Icon,
  badge,
  badgeColor = "indigo",
}) => {
  const badgeClasses = {
    green: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    red: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    indigo: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
    amber: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    slate: "bg-slate-700/40 text-slate-300 border-slate-600/40",
    cyan: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
  }[badgeColor];

  return (
    <div className="glass-card glass-card-hover rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
      {/* 頂部 Header */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          {title}
        </span>
        {Icon && (
          <div className="p-2 rounded-xl bg-slate-800/80 text-indigo-400 border border-slate-700/50">
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      {/* 主數值 */}
      <div className="my-1">
        <div className="text-2xl lg:text-3xl font-bold tracking-tight text-white font-mono">
          {value}
        </div>
      </div>

      {/* 底部輔助數值或標籤 */}
      {(subValue || badge) && (
        <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
          {subValue && (
            <span className="text-slate-400">
              {subLabel && <span className="text-slate-500 mr-1">{subLabel}:</span>}
              <span className="font-medium text-slate-200">{subValue}</span>
            </span>
          )}
          {badge && (
            <span
              className={`px-2 py-0.5 rounded-full border text-[11px] font-medium ml-auto ${badgeClasses}`}
            >
              {badge}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
