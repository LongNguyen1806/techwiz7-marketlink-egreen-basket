import { LoginForm } from '../../components/common/forms/LoginForm';
import './LoginPage.css';

/** G-09. AuthLayout supplies the shell around it. */
export default function LoginPage() {
  return (
    <section className="login-page">
      <LoginForm />
    </section>
  );
}
