"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectOptionGroup {
  label: string;
  options: SelectOption[];
}

export type SelectOptionItem = SelectOption | SelectOptionGroup;

export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  label?: string;
  error?: string;
  options: SelectOptionItem[];
  placeholder?: string;
  onChange?: (value: string) => void;
}

function isOptionGroup(option: SelectOptionItem): option is SelectOptionGroup {
  return "options" in option;
}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    { className, label, error, options, placeholder, onChange, id, ...props },
    ref
  ) => {
    const generatedId = React.useId();
    const selectId = id ?? generatedId;

    return (
      <div className="grid w-full gap-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="text-sm font-medium leading-none text-slate-700 dark:text-slate-300"
          >
            {label}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          className={cn(
            "flex h-9 w-full appearance-none rounded-md border border-slate-200 bg-transparent bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2364748b%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[length:1rem] bg-[right_0.5rem_center] bg-no-repeat px-3 py-1 pr-8 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-950 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-800 dark:focus-visible:ring-slate-300",
            error && "border-red-500 focus-visible:ring-red-500",
            className
          )}
          onChange={(e) => onChange?.(e.target.value)}
          {...props}
        >
          {placeholder && (
            <option key="__placeholder__" value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option, idx) =>
            isOptionGroup(option) ? (
              <optgroup key={`${option.label}-${idx}`} label={option.label}>
                {option.options.map((groupOption, groupOptionIdx) => (
                  <option
                    key={groupOption.value || `opt-${idx}-${groupOptionIdx}`}
                    value={groupOption.value}
                    disabled={groupOption.disabled}
                  >
                    {groupOption.label}
                  </option>
                ))}
              </optgroup>
            ) : (
              <option
                key={option.value || `opt-${idx}`}
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </option>
            )
          )}
        </select>
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }
);
Select.displayName = "Select";

export { Select };
