import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { ApiError } from '../../lib/ApiError';
import { useCategories } from '../../features/catalog/hooks/useCatalog';
import { useFarmerMyProduct, useSaveFarmerProduct } from '../../features/farmer/hooks/useFarmerProducts';
import { productSchema } from '../../features/farmer/schemas/product.schema';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { LazyImage } from '../../components/common/LazyImage';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { Switch } from '../../components/ui/Switch';
import { Textarea } from '../../components/ui/Textarea';
import { usePublicConfigData } from '../../features/catalog/hooks/usePublicConfig';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/farmer/FarmerProductFormPage.css';
const UNITS = ['KG', 'BUNCH', 'PIECE', 'PACK'];
export default function FarmerProductFormPage() {
    const { id } = useParams();
    const productId = id ? Number(id) : NaN;
    const isEdit = Number.isFinite(productId);
    const navigate = useNavigate();
    const maxMb = usePublicConfigData().max_upload_mb;
    const [preview, setPreview] = useState(null);
    const categoriesQuery = useCategories();
    const productQuery = useFarmerMyProduct(productId, isEdit);
    const saveMutation = useSaveFarmerProduct(isEdit ? productId : undefined);
    const form = useForm({
        resolver: zodResolver(productSchema),
        defaultValues: {
            name: '',
            category_id: 0,
            price: '10000',
            unit: 'KG',
            stock_quantity: 10,
            weekly_default_quantity: 20,
            description: '',
            is_available: true,
            image: 'https://images.unsplash.com/photo-1546470427-e212b7d31075?auto=format&fit=crop&w=800&q=80',
        },
    });
    useEffect(() => {
        if (!productQuery.data)
            return;
        const p = productQuery.data;
        form.reset({
            name: p.name,
            category_id: p.category.id,
            price: String(p.price),
            unit: p.unit,
            stock_quantity: p.stock_quantity,
            weekly_default_quantity: p.weekly_default_quantity ?? 0,
            description: p.description ?? '',
            is_available: p.is_available,
            image: p.image ??
                'https://images.unsplash.com/photo-1546470427-e212b7d31075?auto=format&fit=crop&w=800&q=80',
        });
        setPreview(p.image);
    }, [productQuery.data, form]);
    const onFile = (file) => {
        if (!file)
            return;
        const maxBytes = maxMb * 1024 * 1024;
        if (file.size > maxBytes) {
            toast.error(`Image exceeds ${maxMb}MB`);
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const result = typeof reader.result === 'string' ? reader.result : null;
            if (!result)
                return;
            setPreview(result);
            form.setValue('image', result, { shouldValidate: true });
        };
        reader.readAsDataURL(file);
    };
    if (isEdit && productQuery.isLoading)
        return <PageSkeleton />;
    if (isEdit && (productQuery.isError || !productQuery.data)) {
        return (<EmptyState title="Product couldn't be loaded" actionLabel="Try again" onAction={() => productQuery.refetch()}/>);
    }
    return (<div className="farmer-product-form-page">
      <PageHeader title={isEdit ? 'Edit produce' : 'Add produce'} description="Add a photo, set price and stock, then open it for pre-order."/>

      <form className="farmer-product-form-page__form" onSubmit={form.handleSubmit((values) => saveMutation.mutate(values, {
            onSuccess: () => navigate('/farmer/products'),
            onError: (error) => {
                const apiError = ApiError.fromUnknown(error);
                if (Object.keys(apiError.fieldErrors).length > 0) {
                    mapServerErrorsToForm(apiError.fieldErrors, form.setError);
                    return;
                }
                toast.error(apiError.friendlyMessage);
            },
        }))}>
        <div className="farmer-product-form-page__media">
          <div className="farmer-product-form-page__dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => {
            e.preventDefault();
            onFile(e.dataTransfer.files[0]);
        }}>
            {preview || form.watch('image') ? (<LazyImage src={preview ?? form.watch('image')} alt="Preview" className="farmer-product-form-page__preview"/>) : null}
            <p className="farmer-product-form-page__dropzone-title">
              Drag and drop an image or choose a file
            </p>
            <p className="page-primitive__muted-xs">Max {maxMb}MB</p>
            <Input type="file" accept="image/*" className="farmer-product-form-page__file-input" onChange={(e) => onFile(e.target.files?.[0])}/>
          </div>
        </div>

        <div className="farmer-product-form-page__fields">
          <div className="page-primitive__form-field">
            <Input id="name" label="Product name" {...form.register('name')}/>
            {form.formState.errors.name ? (<p className="page-primitive__error">{form.formState.errors.name.message}</p>) : null}
          </div>

          <div className="page-primitive__form-grid-2">
            <div className="page-primitive__form-field">
              <Label htmlFor="category_id">Category</Label>
              <select id="category_id" className="page-primitive__select-full" {...form.register('category_id', { valueAsNumber: true })}>
                <option value={0}>Select category</option>
                {categoriesQuery.data?.map((c) => (<option key={c.id} value={c.id}>
                    {c.name}
                  </option>))}
              </select>
            </div>
            <div className="page-primitive__form-field">
              <Label htmlFor="unit">Unit</Label>
              <select id="unit" className="page-primitive__select-full" {...form.register('unit')}>
                {UNITS.map((u) => (<option key={u} value={u}>
                    {u}
                  </option>))}
              </select>
            </div>
          </div>

          <div className="farmer-product-form-page__grid-3">
            <div className="page-primitive__form-field">
              <Input id="price" type="number" label="Price ($)" {...form.register('price')}/>
            </div>
            <div className="page-primitive__form-field">
              <Input id="stock_quantity" type="number" label="Stock" {...form.register('stock_quantity', { valueAsNumber: true })}/>
            </div>
            <div className="page-primitive__form-field">
              <Input id="weekly_default_quantity" type="number" label="Weekly default stock" {...form.register('weekly_default_quantity', {
        valueAsNumber: true,
    })}/>
            </div>
          </div>

          <div className="page-primitive__form-field">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={4} {...form.register('description')}/>
          </div>

          <div className="farmer-product-form-page__toggle-row">
            <div>
              <p className="page-primitive__font-medium">Open for sale</p>
              <p className="page-primitive__muted-xs">Turn off to pause accepting orders</p>
            </div>
            <Switch checked={form.watch('is_available')} onCheckedChange={(checked) => form.setValue('is_available', checked)}/>
          </div>

          <div className="farmer-product-form-page__actions">
            <Button type="button" variant="outline" onClick={() => navigate('/farmer/products')}>
              Cancel
            </Button>
            <Button type="submit" data-write loading={saveMutation.isPending}>
              Save
            </Button>
          </div>
        </div>
      </form>
    </div>);
}

