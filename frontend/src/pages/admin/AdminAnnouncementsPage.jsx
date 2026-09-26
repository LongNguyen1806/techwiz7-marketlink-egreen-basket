import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  useAdminAnnouncements,
  useCreateAnnouncement,
  useDeleteAnnouncement,
  useToggleAnnouncement,
} from '../../hooks/queries/admin/useAdminAnnouncements';
import { announcementSchema } from '../../schemas/admin/announcement.schema';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { Switch } from '../../components/ui/Switch';
import { Textarea } from '../../components/ui/Textarea';
import { ApiError } from '../../lib/ApiError';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import { formatDateTime } from '../../utils/formatters';
import { audienceLabel } from '../../utils/labels';
import '../../styles/admin/AdminAnnouncementsPage.css';

export default function AdminAnnouncementsPage() {
  const query = useAdminAnnouncements();
  const create = useCreateAnnouncement();
  const remove = useDeleteAnnouncement();
  const toggle = useToggleAnnouncement();
  const form = useForm({
    resolver: zodResolver(announcementSchema),
    defaultValues: {
      title: '',
      content: '',
      audience: 'ALL',
      starts_at: new Date().toISOString().slice(0, 16),
      is_active: true,
    },
  });

  const isActive = form.watch('is_active');

  const onSubmit = (values) => {
    create.mutate(
      {
        title: values.title,
        content: values.content,
        audience: values.audience,
        starts_at: new Date(values.starts_at).toISOString(),
        ends_at: null,
        is_active: values.is_active,
      },
      {
        onSuccess: () => {
          form.reset({
            title: '',
            content: '',
            audience: 'ALL',
            starts_at: new Date().toISOString().slice(0, 16),
            is_active: true,
          });
        },
        onError: (error) => {
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, form.setError);
        },
      },
    );
  };

  return (
    <div className="admin-announcements-page">
      <PageHeader
        title="Announcements"
        description="Publish banners by audience and schedule when they appear."
      />

      <form
        className="admin-announcements-page__create"
        onSubmit={form.handleSubmit(onSubmit)}
      >
        <div className="page-primitive__form-field">
          <Input id="title" label="Title"
            requiredMark {...form.register('title')} />
          {form.formState.errors.title ? (
            <p className="page-primitive__error">{form.formState.errors.title.message}</p>
          ) : null}
        </div>
        <div className="page-primitive__form-field">
          <Label htmlFor="content">Content</Label>
          <Textarea id="content" {...form.register('content')} />
          {form.formState.errors.content ? (
            <p className="page-primitive__error">
              {form.formState.errors.content.message}
            </p>
          ) : null}
        </div>
        <div className="admin-announcements-page__create-row">
          <select className="page-primitive__select" {...form.register('audience')}>
            <option value="ALL">{audienceLabel('ALL')}</option>
            <option value="CUSTOMER">{audienceLabel('CUSTOMER')}</option>
            <option value="FARMER">{audienceLabel('FARMER')}</option>
          </select>
          <Input
            type="datetime-local"
            label="Starts at"
            requiredMark
            className="page-primitive__input-auto"
            {...form.register('starts_at')}
          />
          <div className="page-primitive__inline-row">
            <Switch
              checked={isActive}
              onCheckedChange={(checked) => form.setValue('is_active', checked)}
            />
            <span className="page-primitive__muted-sm">Active</span>
          </div>
          <Button type="submit" loading={create.isPending}>
            Create announcement
          </Button>
        </div>
        {form.formState.errors.starts_at ? (
          <p className="page-primitive__error">
            {form.formState.errors.starts_at.message}
          </p>
        ) : null}
      </form>

      {query.isLoading ? (
        <PageSkeleton />
      ) : !query.data?.results?.length ? (
        <EmptyState
          title="No announcements yet"
          description="Create a banner when you need to reach farmers or shoppers."
        />
      ) : (
        <ul className="admin-announcements-page__list">
          {query.data.results.map((announcement) => (
            <li key={announcement.id} className="admin-announcements-page__item">
              <div className="admin-announcements-page__item-head">
                <div>
                  <p className="page-primitive__semibold">{announcement.title}</p>
                  <p className="page-primitive__muted-sm page-primitive__mt-1">
                    {announcement.content}
                  </p>
                  <div className="admin-announcements-page__meta">
                    <Badge>{audienceLabel(announcement.audience)}</Badge>
                    <span>{formatDateTime(announcement.starts_at)}</span>
                    <Badge variant={announcement.is_active ? 'success' : 'secondary'}>
                      {announcement.is_active ? 'Active' : 'Off'}
                    </Badge>
                  </div>
                </div>
                <div className="page-primitive__actions-row">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      toggle.mutate({
                        id: announcement.id,
                        is_active: !announcement.is_active,
                      })
                    }
                  >
                    {announcement.is_active ? 'Off' : 'On'}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => remove.mutate(announcement.id)}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
