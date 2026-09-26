import { lazy } from 'react';
import { Suspend } from '../Suspend';
import { RequireAuth, RequireRole } from '../guards';
import { CustomerLayout } from '../../layouts/CustomerLayout';
const CustomerDashboard = lazy(() => import('../../pages/customer/CustomerDashboard'));
const CartPage = lazy(() => import('../../pages/customer/CartPage'));
const CheckoutPage = lazy(() => import('../../pages/customer/CheckoutPage'));
const CheckoutSuccessPage = lazy(() => import('../../pages/customer/CheckoutSuccessPage'));
const OrdersPage = lazy(() => import('../../pages/customer/OrdersPage'));
const OrderDetailPage = lazy(() => import('../../pages/customer/OrderDetailPage'));
const EditOrderPage = lazy(() => import('../../pages/customer/EditOrderPage'));
const ReviewOrderPage = lazy(() => import('../../pages/customer/ReviewOrderPage'));
const FavoritesPage = lazy(() => import('../../pages/customer/FavoritesPage'));
const ProfilePage = lazy(() => import('../../pages/customer/ProfilePage'));
const NotificationsPage = lazy(() => import('../../pages/customer/NotificationsPage'));
const ChangePasswordPage = lazy(() => import('../../pages/customer/ChangePasswordPage'));
/** Nested under PublicLayout (see public.routes). */
export const customerRoutes = [
    {
        element: <RequireAuth />,
        children: [
            {
                element: <RequireRole allow={['CUSTOMER']}/>,
                children: [
                    {
                        element: <CustomerLayout />,
                        children: [
                            {
                                path: '/customer',
                                element: (<Suspend>
                    <CustomerDashboard />
                  </Suspend>),
                            },
                            {
                                path: '/customer/cart',
                                element: (<Suspend>
                    <CartPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/checkout',
                                element: (<Suspend>
                    <CheckoutPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/checkout/success',
                                element: (<Suspend>
                    <CheckoutSuccessPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/orders',
                                element: (<Suspend>
                    <OrdersPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/orders/:id',
                                element: (<Suspend>
                    <OrderDetailPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/orders/:id/edit',
                                element: (<Suspend>
                    <EditOrderPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/orders/:id/review',
                                element: (<Suspend>
                    <ReviewOrderPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/favorites',
                                element: (<Suspend>
                    <FavoritesPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/profile',
                                element: (<Suspend>
                    <ProfilePage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/notifications',
                                element: (<Suspend>
                    <NotificationsPage />
                  </Suspend>),
                            },
                            {
                                path: '/customer/password',
                                element: (<Suspend>
                    <ChangePasswordPage />
                  </Suspend>),
                            },
                        ],
                    },
                ],
            },
        ],
    },
];
