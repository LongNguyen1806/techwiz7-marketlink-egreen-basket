import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "../../components/ui/Button";
import { FormAlert } from "../../components/common/forms/FormAlert";
import { FormField } from "../../components/common/forms/FormField";
import { useServerErrors } from "../../components/common/forms/useServerErrors";
import { useAuth } from "../../hooks/authentication/useAuth";
import { loginSchema } from "../../services/common/auth.schemas";
import "../../styles/admin/AdminLoginPage.css";

const FIELDS = ["email", "password"];

export default function AdminLoginPage() {
  const { adminLogin, adminLoginPending } = useAuth();
  const { formError, report, clear } = useServerErrors(FIELDS);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    clear();
    try {
      await adminLogin(values);
    } catch (error) {
      report(error, setError);
    }
  });

  return (
    <section className='admin-login-page'>
      <h1 className='admin-login-page__title'>Staff sign-in</h1>
      <p className='admin-login-page__subtitle'>Use the administrator account issued to you.</p>

      <form className='admin-login-page__form' onSubmit={onSubmit} noValidate>
        <FormAlert message={formError} />

        <FormField id='admin-email' label='Email' type='email' autoComplete='email' error={errors.email?.message} {...register("email")} />
        <FormField id='admin-password' label='Password' type='password' autoComplete='current-password' error={errors.password?.message} {...register("password")} />

        <Button type='submit' size='lg' className='admin-login-page__submit' loading={adminLoginPending}>
          Sign in
        </Button>
      </form>
    </section>
  );
}
