import React, { useState, useEffect, useRef } from "react";

export interface NumericInputProps {
  value: number;
  onCommit: (val: number) => void;
  min?: number;
  max?: number;
  step?: number | string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  autoSelectOnFocus?: boolean;
  ariaLabel?: string;
}

export const NumericInput: React.FC<NumericInputProps> = ({
  value,
  onCommit,
  min,
  max,
  step,
  placeholder,
  className = "",
  disabled = false,
  autoSelectOnFocus = true,
  ariaLabel,
}) => {
  const [text, setText] = useState<string>(() =>
    value !== undefined && !isNaN(value) ? String(value) : ""
  );
  const [isFocused, setIsFocused] = useState<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // 當非聚焦狀態且外部 value 變動時，同步內部文字
  useEffect(() => {
    if (!isFocused) {
      setText(value !== undefined && !isNaN(value) ? String(value) : "");
    }
  }, [value, isFocused]);

  const commitValue = () => {
    const trimmed = text.trim();

    // 判斷是否為空
    if (trimmed === "") {
      // 若清空後未輸入任何數字即按 Enter/離開，安全回退至 min 或原本值
      const fallback = min !== undefined ? min : value;
      setText(String(fallback));
      if (fallback !== value) {
        onCommit(fallback);
      }
      return;
    }

    const parsed = parseFloat(trimmed);

    // 判斷是否為無效數字
    if (isNaN(parsed)) {
      setText(String(value));
      return;
    }

    // 邊界檢查與夾止 (Clamp)
    let finalVal = parsed;
    if (min !== undefined && finalVal < min) {
      finalVal = min;
    }
    if (max !== undefined && finalVal > max) {
      finalVal = max;
    }

    setText(String(finalVal));
    if (finalVal !== value) {
      onCommit(finalVal);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitValue();
      inputRef.current?.blur();
    } else if (e.key === "Escape") {
      e.preventDefault();
      // 還原為原始值
      setText(String(value));
      inputRef.current?.blur();
    }
  };

  const handleBlur = () => {
    setIsFocused(false);
    commitValue();
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    if (autoSelectOnFocus) {
      e.target.select();
    }
  };

  return (
    <input
      ref={inputRef}
      type="text"
      inputMode="decimal"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      placeholder={placeholder}
      className={className}
      aria-label={ariaLabel}
      step={step}
    />
  );
};
