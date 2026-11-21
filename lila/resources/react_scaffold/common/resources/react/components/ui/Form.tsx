import {
  createContext, useContext, useId, type FormEvent, type FormHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";
import { useForm, type HttpError, type SubmitOptions } from "@lila";
import { Button, type ButtonProps } from "./Button";
import { cn } from "./cn";
import { toast } from "./Toast";

type FormApi = ReturnType<typeof useForm<Record<string, any>>>;
const FormContext = createContext<FormApi | null>(null);

/** The nearest <Form>'s useForm() state (errors, processing, data...). */
export function useFormContext(): FormApi | null {
  return useContext(FormContext);
}

export interface FormProps<T extends Record<string, any>> extends Omit<FormHTMLAttributes<HTMLFormElement>, "onSubmit" | "onError"> {
  /** Lila endpoint, e.g. "/login" or "/api/items" (JSON + CSRF). */
  action: string;
  method?: string;
  /** Initial values: one key per field name. */
  initial: T;
  redirect?: string;
  reset?: boolean;
  transform?: (data: T) => unknown;
  /** Toast on success: true = server message, string = custom text. */
  successToast?: boolean | string;
  /** Also toast errors that are not about one field (they always show in the form). */
  errorToast?: boolean;
  /** Render <FormError /> at the top of the form (default true). */
  showErrors?: boolean;
  onSuccess?: (data: any) => void;
  onError?: (error: HttpError) => void;
  /** Client-side checks before sending: return {field: "message"} to stop. */
  validate?: (data: T) => Record<string, string | undefined> | null | undefined | void;
  /** Use an external useForm() instead of the internal one. */
  form?: FormApi;
  children: ReactNode;
}

/**
 * <Form action="/login" initial={{ email: "", password: "" }} redirect="/dashboard">
 *   <Input name="email" type="email" label="Email" required />
 *   <SubmitButton>Sign in</SubmitButton>
 * </Form>
 * 422 errors from Lila appear under each field; other errors at the top (<FormError />).
 */
export function Form<T extends Record<string, any>>({
  action, method = "POST", initial, redirect, reset, transform, successToast, errorToast = false, showErrors = true, onSuccess, onError,
  validate, form: external, className, children, ...props
}: FormProps<T>) {
  const internal = useForm<Record<string, any>>(initial);
  const form = external || internal;
  const options: SubmitOptions<any> & { method?: string } = {
    method, redirect, reset, transform: transform as any,
    onSuccess: (data) => {
      if (successToast) toast.success(typeof successToast === "string" ? successToast : data?.message || data?.msg || "OK");
      onSuccess?.(data);
    },
    onError: (error) => {
      const fieldErrors = Array.isArray(error.data?.errors) && error.data.errors.length;
      if (errorToast && !fieldErrors) toast.error(error.message);
      onError?.(error);
    },
  };
  const send = form.handleSubmit(action, options);
  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const problems = validate?.(form.data as T);
    const found = problems && Object.fromEntries(Object.entries(problems).filter(([, msg]) => msg));
    if (found && Object.keys(found).length) {
      form.setErrors(found as any);
      return;
    }
    send(event);
  };
  return (
    <FormContext.Provider value={form}>
      <form noValidate className={cn("space-y-4", className)} onSubmit={onSubmit} {...props}>
        {showErrors && <FormError />}
        {children}
      </form>
    </FormContext.Provider>
  );
}

interface FieldChrome {
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  /** Element shown at the right of the label (e.g. "Forgot password?"). */
  aside?: ReactNode;
  wrapperClassName?: string;
}

function useBinding(name: string | undefined, explicitError?: string) {
  const form = useContext(FormContext);
  const bound = form && name && name in form.data ? form.field(name) : null;
  return { bound, error: explicitError ?? (form && name ? (form.errors as any)[name] : undefined) };
}

function Chrome({ id, label, hint, error, aside, wrapperClassName, children }: FieldChrome & { id: string; children: ReactNode }) {
  return (
    <div className={cn("field", wrapperClassName)}>
      {(label || aside) && (
        <div className="flex items-center justify-between gap-2">
          {label && <label htmlFor={id} className="field-label">{label}</label>}
          {aside}
        </div>
      )}
      {children}
      {error ? <p id={`${id}-error`} className="field-error">{error}</p> : hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  );
}

export function Input({ label, hint, error, aside, wrapperClassName, className, name, id, ...props }: InputHTMLAttributes<HTMLInputElement> & FieldChrome) {
  const auto = useId();
  const { bound, error: message } = useBinding(name, error);
  const fieldId = id || (bound?.id as string) || auto;
  return (
    <Chrome id={fieldId} label={label} hint={hint} error={message} aside={aside} wrapperClassName={wrapperClassName}>
      <input name={name} {...(bound || {})} id={fieldId} className={cn("form-control", className)}
        aria-invalid={message ? true : undefined} aria-describedby={message ? `${fieldId}-error` : undefined} {...props} />
    </Chrome>
  );
}

export function Textarea({ label, hint, error, aside, wrapperClassName, className, name, id, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & FieldChrome) {
  const auto = useId();
  const { bound, error: message } = useBinding(name, error);
  const fieldId = id || (bound?.id as string) || auto;
  return (
    <Chrome id={fieldId} label={label} hint={hint} error={message} aside={aside} wrapperClassName={wrapperClassName}>
      <textarea name={name} {...((bound as any) || {})} id={fieldId} className={cn("form-control", className)} aria-invalid={message ? true : undefined} {...props} />
    </Chrome>
  );
}

export interface SelectOption {
  value: string | number;
  label: ReactNode;
}

export function Select({ label, hint, error, aside, wrapperClassName, className, name, id, options, placeholder, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & FieldChrome & { options?: Array<SelectOption | string>; placeholder?: string }) {
  const auto = useId();
  const { bound, error: message } = useBinding(name, error);
  const fieldId = id || (bound?.id as string) || auto;
  return (
    <Chrome id={fieldId} label={label} hint={hint} error={message} aside={aside} wrapperClassName={wrapperClassName}>
      <select name={name} {...((bound as any) || {})} id={fieldId} className={cn("form-control", className)} aria-invalid={message ? true : undefined} {...props}>
        {placeholder && <option value="">{placeholder}</option>}
        {(options || []).map((option) => {
          const item = typeof option === "string" ? { value: option, label: option } : option;
          return <option key={String(item.value)} value={item.value}>{item.label}</option>;
        })}
        {children}
      </select>
    </Chrome>
  );
}

export function Checkbox({ label, hint, error, wrapperClassName, name, id, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & FieldChrome) {
  const auto = useId();
  const { bound, error: message } = useBinding(name, error);
  const fieldId = id || (bound?.id as string) || auto;
  return (
    <div className={cn("field", wrapperClassName)}>
      <label htmlFor={fieldId} className="inline-flex cursor-pointer items-center gap-2 text-sm">
        <input type="checkbox" name={name} {...(bound || {})} id={fieldId} className="h-4 w-4 accent-primary" {...props} />
        {label}
      </label>
      {message ? <p className="field-error">{message}</p> : hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  );
}

/** Submit button bound to the nearest <Form> (spinner while sending). */
export function SubmitButton({ children, className, ...props }: ButtonProps) {
  const form = useContext(FormContext);
  return (
    <Button type="submit" loading={form?.processing} className={cn("w-full", className)} {...props}>
      {children}
    </Button>
  );
}

/** Errors that are not about one field (401, 429, "Invalid email or password"...). */
export function FormError({ className }: { className?: string }) {
  const form = useContext(FormContext);
  const message = form?.errors._form;
  if (!message) return null;
  return <p role="alert" className={cn("rounded-xl bg-danger/10 px-4 py-2 text-sm text-danger", className)}>{message}</p>;
}

/** Success message returned by the server (`message`/`msg`). */
export function FormMessage({ className }: { className?: string }) {
  const form = useContext(FormContext);
  if (!form?.message) return null;
  return <p role="status" className={cn("rounded-xl bg-success/10 px-4 py-2 text-sm text-success", className)}>{form.message}</p>;
}
