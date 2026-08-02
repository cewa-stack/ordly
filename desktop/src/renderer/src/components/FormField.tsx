import * as React from "react";

interface FormFieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "className"> {
  label: string;
  icon?: React.ReactNode;
  trailing?: React.ReactNode;
  onTrailingClick?: () => void;
  error?: boolean;
}

/** Pole formularza z wiodaca ikona - 1:1 z mobile/src/components/FormField.tsx. */
export const FormField = React.forwardRef<HTMLInputElement, FormFieldProps>(function FormField(
  { label, icon, trailing, onTrailingClick, error, onFocus, onBlur, ...inputProps },
  ref
) {
  const [focused, setFocused] = React.useState(false);
  return (
    <label className="flex flex-col gap-1.5">
      <span className={`text-caption ${focused ? "text-primary" : "text-text-secondary"}`}>{label}</span>
      <div
        className={`ordly-field-row ${focused ? "focused" : ""} ${error ? "!border-danger" : ""}`}
      >
        {icon}
        <input
          {...inputProps}
          ref={ref}
          className="h-full flex-1 border-0 bg-transparent p-0 text-body text-text placeholder:text-text-dim focus:outline-none"
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
        />
        {trailing ? (
          onTrailingClick ? (
            <button type="button" onClick={onTrailingClick} className="text-text-secondary">
              {trailing}
            </button>
          ) : (
            trailing
          )
        ) : null}
      </div>
    </label>
  );
});
