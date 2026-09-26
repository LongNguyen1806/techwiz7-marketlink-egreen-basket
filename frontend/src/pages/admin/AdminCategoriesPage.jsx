import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';

import {
  useAdminCategories,
  useCreateCategory,
  useDeleteCategory,
  useReorderCategories,
} from '../../hooks/queries/admin/useAdminCategories';
import { categorySchema } from '../../schemas/admin/category.schema';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { ApiError } from '../../lib/ApiError';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import { CategoryIcon } from '../../components/common/badges/CategoryIcon';
import { IconPicker } from '../../components/admin/IconPicker';
import '../../styles/admin/AdminCategoriesPage.css';

function SortableRow({ cat, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: cat.id,
  });

  const bindSortableNode = (node) => {
    setNodeRef(node);
    if (!node) return;
    node.style.transform = CSS.Transform.toString(transform) ?? '';
    node.style.transition = transition ?? '';
  };

  const inUse = cat.product_count > 0;

  return (
    <div ref={bindSortableNode} className="page-primitive__sort-row">
      <button
        type="button"
        className="page-primitive__grip-btn"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="page-primitive__icon-md" />
      </button>
      <CategoryIcon icon={cat.icon} className="admin-categories-page__icon" />
      <div className="page-primitive__flex-1">
        <p className="page-primitive__font-medium">{cat.name}</p>
        <p className="page-primitive__muted-xs">
          {cat.product_count === 1 ? '1 product' : `${cat.product_count} products`}
        </p>
      </div>
      {inUse ? (
        <span className="admin-categories-page__locked">In use</span>
      ) : null}
      <Button
        size="sm"
        variant="destructive"
        disabled={inUse}
        title={
          inUse
            ? 'Move or remove its products first — a category in use cannot be deleted.'
            : undefined
        }
        onClick={() => onDelete(cat.id)}
      >
        Delete
      </Button>
    </div>
  );
}

export default function AdminCategoriesPage() {
  const query = useAdminCategories();
  const [items, setItems] = useState([]);
  const [syncedData, setSyncedData] = useState(query.data);
  const form = useForm({
    resolver: zodResolver(categorySchema),
    defaultValues: { name: '', icon: 'leaf' },
  });

  if (query.data !== syncedData) {
    setSyncedData(query.data);
    if (query.data) setItems(query.data);
  }

  const sensors = useSensors(useSensor(PointerSensor));
  const reorder = useReorderCategories();
  const create = useCreateCategory();
  const remove = useDeleteCategory();

  const onDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((i) => i.id === active.id);
    const newIndex = items.findIndex((i) => i.id === over.id);
    const next = arrayMove(items, oldIndex, newIndex);
    setItems(next);
    reorder.mutate(
      next.map((i) => i.id),
      {
        onSuccess: (data) => setItems(data),
      },
    );
  };

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) {
    return (
      <EmptyState
        title="Categories couldn't be loaded"
        actionLabel="Try again"
        onAction={() => query.refetch()}
      />
    );
  }

  return (
    <div className="admin-categories-page">
      <PageHeader
        title="Produce categories"
        description="Drag to reorder how categories appear to shoppers."
      />

      <form
        className="admin-categories-page__create"
        onSubmit={form.handleSubmit((values) => {
          create.mutate(values, {
            onSuccess: () => form.reset({ name: '', icon: 'leaf' }),
            onError: (error) => {
              mapServerErrorsToForm(
                ApiError.fromUnknown(error).fieldErrors,
                form.setError,
              );
            },
          });
        })}
      >
        <div className="admin-categories-page__create-row">
          <div className="page-primitive__field-tight">
            <Input
              label="Name"
              requiredMark
              className="page-primitive__input-name-wide"
              {...form.register('name')}
            />
            {form.formState.errors.name ? (
              <p className="page-primitive__error">{form.formState.errors.name.message}</p>
            ) : null}
          </div>
          <Button type="submit" loading={create.isPending}>
            Add
          </Button>
        </div>
        <IconPicker
          value={form.watch('icon') ?? 'leaf'}
          onChange={(icon) => form.setValue('icon', icon, { shouldDirty: true })}
        />
      </form>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={onDragEnd}
      >
        <SortableContext
          items={items.map((i) => i.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="admin-categories-page__list">
            {items.map((cat) => (
              <SortableRow key={cat.id} cat={cat} onDelete={(id) => remove.mutate(id)} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
