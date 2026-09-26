import { PageHeader } from '../../components/common/PageHeader';
import { Card, CardContent } from '../../components/ui/Card';
import { ChangePasswordForm } from './ChangePasswordForm';
import '../../styles/auth/ChangePasswordPage.css';

export default function ChangePasswordPage() {
  return (
    <div>
      <PageHeader
        title="Change password"
        description="You stay signed in on this device. Every other device will be signed out after you save."
      />
      <Card className="change-password-page__card">
        <CardContent className="change-password-page__content">
          <ChangePasswordForm />
        </CardContent>
      </Card>
    </div>
  );
}
