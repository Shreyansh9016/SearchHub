import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../components/Auth";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function validate(values, mode) {
  const errors = {};
  if (mode === "register" && !values.name.trim()) errors.name = "Name is required.";
  if (!EMAIL_RE.test(values.email.trim())) errors.email = "Enter a valid email address.";
  if (mode === "register" && values.password.length < 8) errors.password = "Use at least 8 characters.";
  if (mode === "login" && !values.password) errors.password = "Password is required.";
  return errors;
}

function Field({ id, label, type = "text", value, onChange, error, autoComplete }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        aria-invalid={error ? "true" : "false"}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && (
        <span id={`${id}-error`} className="field-error">
          {error}
        </span>
      )}
    </div>
  );
}

function AuthForm({ mode }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [values, setValues] = useState({ name: "", email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  if (user) return <Navigate to={location.state?.from || "/search"} replace />;

  const set = (field) => (event) => setValues((v) => ({ ...v, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    const found = validate(values, mode);
    setErrors(found);
    setServerError("");
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    try {
      if (isLogin) await login(values.email.trim(), values.password);
      else await register(values.name.trim(), values.email.trim(), values.password);
      navigate(location.state?.from || "/search", { replace: true });
    } catch (error) {
      setServerError(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit} noValidate>
        <div className="brand auth-brand">
          <span className="brand-mark" aria-hidden="true">
            ⌕
          </span>
          SearchHub
        </div>
        <h1>{isLogin ? "Log in" : "Create your account"}</h1>
        {serverError && (
          <p className="form-error" role="alert">
            {serverError}
          </p>
        )}
        {!isLogin && (
          <Field id="name" label="Name" value={values.name} onChange={set("name")} error={errors.name} autoComplete="name" />
        )}
        <Field
          id="email"
          label="Email"
          type="email"
          value={values.email}
          onChange={set("email")}
          error={errors.email}
          autoComplete="email"
        />
        <Field
          id="password"
          label="Password"
          type="password"
          value={values.password}
          onChange={set("password")}
          error={errors.password}
          autoComplete={isLogin ? "current-password" : "new-password"}
        />
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? "Please wait…" : isLogin ? "Log in" : "Sign up"}
        </button>
        <p className="muted auth-switch">
          {isLogin ? (
            <>
              New here? <Link to="/register" state={location.state}>Create an account</Link>
            </>
          ) : (
            <>
              Already registered? <Link to="/login" state={location.state}>Log in</Link>
            </>
          )}
        </p>
      </form>
    </div>
  );
}

export const LoginPage = () => <AuthForm mode="login" />;
export const RegisterPage = () => <AuthForm mode="register" />;
