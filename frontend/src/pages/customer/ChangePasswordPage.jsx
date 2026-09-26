import { ChangePasswordForm } from '../../components/common/forms/ChangePasswordForm';
import { PageHeader } from '../../components/common/PageHeader';
import '../../styles/customer/ChangePasswordPage.css';

/** C-11 (AU-07). The same form serves F-11 and A-12 from their own routes. */
export default function ChangePasswordPage() {
  return (
    <section className="change-password-page">
      <PageHeader
        title="Change password"
        description="Your other devices will be signed out. This one stays signed in."
      />
      <div className="change-password-page__panel">
        <ChangePasswordForm />
      </div>
    </section>
  );
}
