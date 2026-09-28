"""Seed realistic production-like sample data for MarketLink.

Wipes old data cleanly, resets auto-increment IDs to 1 across all business tables,
and seeds:
- 1 Superuser Admin
- 6 Real Wholesale/Traditional Markets in Ho Chi Minh City, plus 1 closed for renovation
- 5 Produce Categories with unique icons
- 6 Approved Farmers with Stalls & Pickup Slots across the 6 Markets, plus 2 awaiting approval
- 20 Customers (English names, Vietnamese phone format), 2 of them with repeated no-shows
- ~80 Real Products categorized correctly, plus a review queue (pending, rejected, hidden)
- ~5 months of orders in every status, dated when they were placed, so the admin
  dashboard, reports and month picker have something to show
- Realistic Reviews for Farmers and Products

Default password for all seeded users: Pass@123
"""

import os
import random
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import CustomerProfile, CustomUser, FarmerProfile, FarmerStatus, Role
from catalog.models import Category, ModerationAction, PriceGuideline, Product, ProductMarket, ReviewStatus, Unit
from marketlink_core.policies.roles import RoleCode
from markets.models import DayOfWeek, FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import (
    ActorRole,
    ChangeReason,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Transition,
)
from reviews.models import FarmerReview, ProductReview
from system.auto_flags import scan_existing

DEFAULT_PASSWORD = "Pass@123"

MARKET_DATA = [
    {
        "name": "Thu Duc Wholesale Agricultural Market",
        "address": "141 Đỗ Mười, Phường Tam Bình, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.869713"),
        "longitude": Decimal("106.728056"),
        "open_time": time(4, 0),
        "close_time": time(11, 0),
        "description": (
            "The largest wholesale market in Ho Chi Minh City specializing in fresh fruits and vegetables "
            "sourced directly from the Mekong Delta, Southeast Region, Da Lat, and international imports. "
            "Peak wholesale trading occurs between 21:00 and 05:00."
        ),
    },
    {
        "name": "Hoc Mon Wholesale Market",
        "address": "Nguyễn Thị Sóc, Xã Xuân Thới Sơn, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.859739"),
        "longitude": Decimal("106.600659"),
        "open_time": time(4, 0),
        "close_time": time(11, 0),
        "description": (
            "The primary supply hub for pork in Ho Chi Minh City, combined with high-volume distribution "
            "of fresh vegetables, tubers, mushrooms, and assorted spices. Peak trading hours run from 22:00 to 06:00."
        ),
    },
    {
        "name": "Binh Dien Wholesale Market",
        "address": "Quản Trọng Linh, Phường Bình Đông, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.702026"),
        "longitude": Decimal("106.608376"),
        "open_time": time(4, 0),
        "close_time": time(11, 0),
        "description": (
            "The largest integrated wholesale hub for agricultural and aquatic products in Southern Vietnam; "
            "specializes in live/frozen seafood, livestock, poultry, and dedicated market halls for vegetables and fruits."
        ),
    },
    {
        "name": "Ba Chieu Market",
        "address": "Phan Đăng Lưu, Phường Gia Định, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.801875"),
        "longitude": Decimal("106.698760"),
        "open_time": time(5, 0),
        "close_time": time(20, 0),
        "description": (
            "A major traditional market where surrounding perimeters gather fresh produce arriving from regional "
            "provinces past midnight, trading both small-scale wholesale and daily retail at affordable rates."
        ),
    },
    {
        "name": "Binh Tay Market (Cho Lon)",
        "address": "57A Tháp Mười, Phường Bình Tây, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.749297"),
        "longitude": Decimal("106.650728"),
        "open_time": time(6, 0),
        "close_time": time(19, 0),
        "description": (
            "The premier wholesale center in Ho Chi Minh City for dried agricultural produce, dried mushrooms, "
            "culinary spices, edible nuts, and packaged agricultural commodities."
        ),
    },
    {
        "name": "Tan Dinh Market",
        "address": "336 Hai Bà Trưng, Phường Tân Định, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.790451"),
        "longitude": Decimal("106.688785"),
        "open_time": time(5, 30),
        "close_time": time(18, 30),
        "description": (
            "A central retail market offering a diverse selection of fresh daily groceries, premium hand-picked "
            "grade-A fruits, and regional prepared culinary specialties."
        ),
    },
]

CATEGORY_DATA = [
    ("Fresh Vegetables", "carrot", 1),
    ("Fresh Fruits", "apple", 2),
    ("Spices & Condiments", "chilli", 3),
    ("Rice & Grains", "wheat", 4),
    ("Tea & Coffee", "leaf", 5),
]

PRICE_GUIDELINES = {
    "Fresh Vegetables": {
        Unit.KG: ("0.30", "10.00", 2000),
        Unit.BUNCH: ("0.20", "5.00", 2000),
        Unit.EACH: ("0.20", "10.00", 2000),
        Unit.BAG: ("0.50", "15.00", 1000),
        Unit.PACK: ("0.30", "10.00", 1000),
    },
    "Fresh Fruits": {
        Unit.KG: ("0.30", "20.00", 2000),
        Unit.BUNCH: ("0.50", "10.00", 1000),
        Unit.EACH: ("0.50", "30.00", 1000),
        Unit.BOX: ("1.00", "30.00", 500),
    },
    "Spices & Condiments": {
        Unit.KG: ("0.50", "50.00", 500),
        Unit.BAG: ("0.30", "20.00", 1000),
        Unit.PACK: ("0.30", "20.00", 1000),
    },
    "Rice & Grains": {
        Unit.KG: ("0.50", "20.00", 2000),
        Unit.BAG: ("0.50", "60.00", 1000),
    },
    "Tea & Coffee": {
        Unit.BAG: ("1.00", "50.00", 500),
        Unit.PACK: ("1.00", "50.00", 500),
    },
}

FARMER_DATA = [
    {
        "email": "farmer_01@marketlink.com",
        "stall_name": "Thu Duc Fresh Organics",
        "contact_person": "Nguyen Van Tu",
        "phone": "0901000001",
        "market_idx": 0,
        "stall_label": "Zone A, Stalls 12-14 (Produce Wholesale Wing)",
    },
    {
        "email": "farmer_02@marketlink.com",
        "stall_name": "Hoc Mon Agri Supply",
        "contact_person": "Tran Thi Mai",
        "phone": "0901000002",
        "market_idx": 1,
        "stall_label": "Hall 2, Stall 08 (Vegetables & Spices)",
    },
    {
        "email": "farmer_03@marketlink.com",
        "stall_name": "Binh Dien Farm Direct",
        "contact_person": "Le Hoang Nam",
        "phone": "0901000003",
        "market_idx": 2,
        "stall_label": "Hall B, Stalls 45-46 (Fresh Fruit Hub)",
    },
    {
        "email": "farmer_04@marketlink.com",
        "stall_name": "Ba Chieu Market Garden",
        "contact_person": "Pham Thi Lan",
        "phone": "0901000004",
        "market_idx": 3,
        "stall_label": "Perimeter Row C, Stall 22",
    },
    {
        "email": "farmer_05@marketlink.com",
        "stall_name": "Cho Lon Spices & Grains",
        "contact_person": "Dang Van Phuc",
        "phone": "0901000005",
        "market_idx": 4,
        "stall_label": "Courtyard Center, Stalls 101-102",
    },
    {
        "email": "farmer_06@marketlink.com",
        "stall_name": "Tan Dinh Select Produce",
        "contact_person": "Bui Thi Hoa",
        "phone": "0901000006",
        "market_idx": 5,
        "stall_label": "Main Entrance East, Stall 05",
    },
]

CUSTOMER_NAMES = [
    "John Smith", "Emily Johnson", "Michael Williams", "Jessica Brown", "David Jones",
    "Sarah Garcia", "James Miller", "Jennifer Davis", "Robert Rodriguez", "Lisa Martinez",
    "William Hernandez", "Mary Lopez", "Richard Gonzalez", "Patricia Wilson", "Thomas Anderson",
    "Barbara Thomas", "Charles Taylor", "Elizabeth Moore", "Daniel Jackson", "Susan Martin",
]

CUSTOMER_ADDRESSES = [
    "12 Le Loi Street, Ben Nghe Ward, Ho Chi Minh City",
    "45 Nguyen Thi Minh Khai, Da Kao Ward, Ho Chi Minh City",
    "88 Pasteur Street, Ben Nghe Ward, Ho Chi Minh City",
    "102 Nam Ky Khoi Nghia, Vo Thi Sau Ward, Ho Chi Minh City",
    "15 Tran Quoc Thao, Ward 9, Ho Chi Minh City",
    "240 Nguyen Dinh Chieu, Ward 6, Ho Chi Minh City",
    "19 Doan Van Bo, Ward 12, Ho Chi Minh City",
    "55 Hoang Dieu, Ward 6, Ho Chi Minh City",
    "78 An Duong Vuong, Ward 9, Ho Chi Minh City",
    "120 Tran Hung Dao, Ward 7, Ho Chi Minh City",
    "33 Hau Giang, Ward 2, Ho Chi Minh City",
    "400 Nguyen Van Linh, Tan Phu Ward, Ho Chi Minh City",
    "65 Nguyen Thi Thap, Tan Quy Ward, Ho Chi Minh City",
    "210 Pham The Hien, Ward 4, Ho Chi Minh City",
    "95 Ba Thang Hai, Ward 11, Ho Chi Minh City",
    "180 Le Dai Hanh, Ward 15, Ho Chi Minh City",
    "52 Phan Dang Luu, Ward 5, Ho Chi Minh City",
    "84 Bach Dang, Ward 24, Ho Chi Minh City",
    "310 Dien Bien Phu, Ward 25, Ho Chi Minh City",
    "68 Vo Van Ngan, Linh Chieu Ward, Ho Chi Minh City",
]

PRODUCTS_DATA = [
    ("Fresh Vegetables", "Water Spinach (Rau Muong)", Unit.BUNCH, "0.80", 0, "Crisp, organically grown fresh water spinach."),
    ("Fresh Vegetables", "Bok Choy (Cai Ngot)", Unit.KG, "1.20", 0, "Tender sweet bok choy, harvested fresh daily."),
    ("Fresh Vegetables", "Mustard Greens (Cai Xanh)", Unit.KG, "1.10", 0, "Slightly peppery and nutritious mustard greens."),
    ("Fresh Vegetables", "Malabar Spinach (Mong Toi)", Unit.BUNCH, "0.75", 0, "Fresh malabar spinach, ideal for traditional soup."),
    ("Fresh Vegetables", "Red Amaranth (Rau Den)", Unit.BUNCH, "0.75", 0, "Sweet red amaranth leaves packed with iron."),
    ("Fresh Vegetables", "Green Cabbage (Bap Cai)", Unit.KG, "1.00", 1, "Firm, heavy green cabbage heads from Da Lat."),
    ("Fresh Vegetables", "Green Broccoli (Sup Lo Xanh)", Unit.KG, "2.25", 1, "Crisp, deep-green broccoli crowns rich in vitamins."),
    ("Fresh Vegetables", "White Cauliflower (Sup Lo Trang)", Unit.KG, "2.10", 1, "Dense, pristine white cauliflower florets."),
    ("Fresh Vegetables", "Da Lat Carrots (Ca Rot)", Unit.KG, "1.25", 1, "Sweet, crunchy orange carrots grown in Da Lat soil."),
    ("Fresh Vegetables", "Yellow Potatoes (Khoai Tay)", Unit.KG, "1.50", 1, "Smooth-skinned starchy yellow potatoes."),
    ("Fresh Vegetables", "Honey Sweet Potatoes (Khoai Lang Mat)", Unit.KG, "1.40", 3, "Naturally sweet orange-fleshed sweet potatoes."),
    ("Fresh Vegetables", "Yellow Onions (Hanh Tay)", Unit.KG, "1.60", 3, "Versatile, flavorful yellow onions."),
    ("Fresh Vegetables", "Vine-Ripened Tomatoes (Ca Chua)", Unit.KG, "1.40", 3, "Juicy, ripe red tomatoes perfect for salads or cooking."),
    ("Fresh Vegetables", "Baby Cucumbers (Dua Leo)", Unit.KG, "1.10", 3, "Crisp, thin-skinned refreshing cucumbers."),
    ("Fresh Vegetables", "Pumpkin (Bi Do)", Unit.KG, "0.90", 3, "Dense, sweet pumpkin rich in beta-carotene."),
    ("Fresh Vegetables", "Winter Melon (Bi Dao)", Unit.KG, "0.80", 5, "Mild, cooling winter melon for light soups."),
    ("Fresh Vegetables", "Sweet Luffa (Muop Huong)", Unit.KG, "1.10", 5, "Fragrant, tender angled luffa gourds."),
    ("Fresh Vegetables", "Bottle Gourd (Trai Bau)", Unit.EACH, "0.75", 5, "Fresh light-green bottle gourd."),
    ("Fresh Vegetables", "Fresh Scallions (Hanh La)", Unit.BUNCH, "0.50", 5, "Aromatic fresh green scallions."),
    ("Fresh Vegetables", "Bird's Eye Chillies (Ot Hiem)", Unit.PACK, "0.75", 1, "Spicy, vibrant red bird's eye chillies (100g)."),
    ("Fresh Vegetables", "Purple Garlic (Toi Ly Son)", Unit.BAG, "1.40", 1, "Intensely aromatic purple garlic bulbs (500g)."),
    ("Fresh Vegetables", "Napa Cabbage (Cai Thao)", Unit.KG, "1.30", 5, "Crisp and sweet napa cabbage for stir-fries and kimchi."),
    ("Fresh Vegetables", "Crisp Celery (Can Tay)", Unit.KG, "1.75", 5, "Aromatic, crunchy stalks of farm-fresh celery."),
    ("Fresh Vegetables", "Fresh Lemongrass (Sa Cay)", Unit.BUNCH, "0.60", 1, "Fragrant lemongrass stalks, freshly harvested."),

    ("Fresh Fruits", "Red Watermelon (Dua Hau)", Unit.KG, "0.70", 2, "Sweet, juicy seedless red watermelon."),
    ("Fresh Fruits", "Ri6 Durian (Sau Rieng Ri6)", Unit.KG, "4.50", 2, "Creamy, highly aromatic golden Ri6 durian from Ben Tre."),
    ("Fresh Fruits", "Crunchy Jackfruit (Mit Thai)", Unit.KG, "1.75", 2, "Golden, sweet, fragrant jackfruit segments."),
    ("Fresh Fruits", "Hoa Loc Mango (Xoai Cat Hoa Loc)", Unit.KG, "2.75", 2, "The finest aromatic, fiber-less mango from Tien Giang."),
    ("Fresh Fruits", "Crisp Guava (Oi Nu Hoang)", Unit.KG, "1.25", 2, "Crunchy Queen guava with minimal seeds."),
    ("Fresh Fruits", "An Phuoc Plum (Man An Phuoc)", Unit.KG, "2.25", 2, "Juicy, crisp bell-fruit plums."),
    ("Fresh Fruits", "Cavendish Bananas (Chuoi Gia)", Unit.BUNCH, "1.50", 0, "Naturally ripened sweet Cavendish bananas."),
    ("Fresh Fruits", "Sanh Green Orange (Cam Sanh)", Unit.KG, "1.75", 0, "Juicy green-skinned oranges from Vinh Long."),
    ("Fresh Fruits", "Sweet Tangerines (Quyt Duong)", Unit.KG, "2.25", 0, "Easy-to-peel sweet Southern tangerines."),
    ("Fresh Fruits", "Green-Skin Pomelo (Buoi Da Xanh)", Unit.EACH, "3.25", 0, "Succulent pink-fleshed pomelo with sweet juice sacs."),
    ("Fresh Fruits", "Red Flesh Dragon Fruit (Thanh Long Ruot Do)", Unit.KG, "1.90", 0, "Vibrant ruby-red dragon fruit from Binh Thuan."),
    ("Fresh Fruits", "Ripe Papaya (Du Du Chin Cay)", Unit.KG, "0.90", 0, "Naturally tree-ripened orange papaya."),
    ("Fresh Fruits", "Java Rambutan (Chom Chom)", Unit.KG, "2.25", 2, "Sweet, easy-to-separate rambutan fruit."),
    ("Fresh Fruits", "Xuong Longan (Nhan Xuong)", Unit.KG, "2.50", 2, "Thick-fleshed, fragrant sweet longan."),
    ("Fresh Fruits", "Thieu Lychee (Vai Thieu)", Unit.KG, "3.25", 2, "Classic sweet lychee with delicate floral notes."),
    ("Fresh Fruits", "Da Lat Strawberries (Dau Tay)", Unit.BOX, "4.75", 5, "Hand-picked ripe red strawberries from Da Lat farms (500g)."),
    ("Fresh Fruits", "Crisp Red Apple (Tao Do)", Unit.KG, "3.00", 5, "Crisp, sweet red apples."),
    ("Fresh Fruits", "Fragrant Asian Pear (Le)", Unit.KG, "2.50", 5, "Refreshing, juicy Asian sweet pears."),
    ("Fresh Fruits", "Seedless Black Grapes (Nho Den)", Unit.BOX, "4.25", 5, "Sweet, crunchy seedless black table grapes (500g)."),
    ("Fresh Fruits", "Japanese Cantaloupe (Dua Luoi)", Unit.EACH, "2.75", 5, "Fragrant green-fleshed cantaloupe melon."),
    ("Fresh Fruits", "Mangosteen (Mang Cut)", Unit.KG, "3.75", 2, "Queen of fruits: sweet, tangy white segments."),
    ("Fresh Fruits", "034 Avocado (Bo 034)", Unit.KG, "2.50", 5, "Creamy, rich elongated 034 avocado from Lam Dong."),
    ("Fresh Fruits", "Passion Fruit (Chanh Day)", Unit.KG, "1.75", 5, "Tangy, intensely aromatic purple passion fruit."),
    ("Fresh Fruits", "Custard Apple (Mang Cau Ta)", Unit.KG, "3.00", 2, "Fragrant custard apple with sweet, delicate segments."),

    ("Spices & Condiments", "Natural Sea Salt (Muoi Bien)", Unit.BAG, "0.60", 4, "Pure unrefined crystalline sea salt from Ninh Thuan (1kg)."),
    ("Spices & Condiments", "Pure Cane Sugar (Duong Mia)", Unit.BAG, "1.20", 4, "Traditional golden unrefined cane sugar (1kg)."),
    ("Spices & Condiments", "Monosodium Glutamate MSG (Bot Ngot)", Unit.BAG, "1.75", 4, "High-purity food-grade umami seasoning crystals (400g)."),
    ("Spices & Condiments", "Rich Broth Seasoning (Hat Nem)", Unit.PACK, "1.90", 4, "Savory seasoning powder blend for rich soups (400g)."),
    ("Spices & Condiments", "Phu Quoc Black Pepper (Tieu Den)", Unit.PACK, "2.40", 4, "Whole pungent black peppercorns from Phu Quoc (200g)."),
    ("Spices & Condiments", "Pure Turmeric Powder (Tinh Bot Nghe)", Unit.PACK, "2.25", 4, "Finely ground organic yellow turmeric powder (100g)."),
    ("Spices & Condiments", "Toasted Garlic Powder (Bot Toi)", Unit.PACK, "1.75", 4, "Savory aromatic roasted garlic seasoning powder (100g)."),
    ("Spices & Condiments", "Sweet Onion Powder (Bot Hanh)", Unit.PACK, "1.75", 4, "Mild, sweet dehydrated onion seasoning (100g)."),
    ("Spices & Condiments", "Smoked Chilli Powder (Bot Ot)", Unit.PACK, "1.60", 4, "Vibrant red ground chilli spice powder (100g)."),
    ("Spices & Condiments", "Yen Bai Cinnamon Sticks (Que Cay)", Unit.PACK, "2.75", 4, "High-oil fragrant rolled cinnamon bark sticks (200g)."),

    ("Rice & Grains", "ST25 Fragrant Jasmine Rice (Gao ST25)", Unit.BAG, "9.00", 4, "World award-winning fragrant long-grain rice (5kg)."),
    ("Rice & Grains", "Black Glutinous Rice (Nep Cam)", Unit.BAG, "3.25", 4, "Rich antioxidant purple-black sticky rice (1kg)."),
    ("Rice & Grains", "Whole Wheat Grain (Lua Mi)", Unit.BAG, "2.25", 4, "Whole nutritious wheat grains for baking or porridge (1kg)."),
    ("Rice & Grains", "Green Mung Beans (Dau Xanh)", Unit.BAG, "2.10", 4, "Polished whole green mung beans (1kg)."),
    ("Rice & Grains", "Small Black Beans (Dau Den Xanh Long)", Unit.BAG, "2.25", 4, "Premium green-kernel black beans (1kg)."),
    ("Rice & Grains", "Small Red Beans (Dau Do)", Unit.BAG, "2.40", 4, "Nutritious small red adzuki beans (1kg)."),
    ("Rice & Grains", "Non-GMO Soybeans (Dau Nanh)", Unit.BAG, "1.75", 4, "High-protein golden soybeans for fresh milk and tofu (1kg)."),
    ("Rice & Grains", "Roasted Peanuts (Dau Phong)", Unit.BAG, "2.00", 4, "Aromatic crunchy roasted peanuts from Cu Chi (500g)."),
    ("Rice & Grains", "Binh Phuoc Roasted Cashews (Hat Dieu)", Unit.BAG, "6.50", 4, "Crisp, buttery salted roasted cashew nuts (500g)."),
    ("Rice & Grains", "Dong Thap Dried Lotus Seeds (Hat Sen)", Unit.BAG, "7.50", 4, "Sweet, nutrient-rich peeled dried lotus seeds (500g)."),
    ("Rice & Grains", "Roasted Watermelon Seeds (Hat Dua)", Unit.BAG, "2.75", 4, "Traditional festive roasted red watermelon seeds (500g)."),
    ("Rice & Grains", "Raw Pumpkin Seeds (Hat Bi)", Unit.BAG, "3.25", 4, "Shelled natural raw green pumpkin seeds (250g)."),
    ("Rice & Grains", "Roasted Sunflower Seeds (Hat Huong Duong)", Unit.BAG, "1.75", 4, "Lightly salted crisp roasted sunflower seeds (500g)."),
    ("Rice & Grains", "Organic Chia Seeds (Hat Chia)", Unit.BAG, "4.50", 4, "Premium nutrient-dense raw black chia seeds (250g)."),
    ("Rice & Grains", "Roasted Almonds (Hanh Nhan)", Unit.BAG, "7.00", 4, "Crunchy whole roasted California almonds (500g)."),
    ("Rice & Grains", "Shelled Walnuts (Oc Cho)", Unit.BAG, "8.00", 4, "Rich omega-3 shelled walnut halves (500g)."),
    ("Rice & Grains", "Dak Lak Macadamia Nuts (Hat Macca)", Unit.BAG, "8.75", 4, "Cracked-shell buttery macadamia nuts (500g)."),
    ("Rice & Grains", "Roasted Chestnuts (Hat De)", Unit.BAG, "4.00", 4, "Sweet, warm roasted whole chestnuts (500g)."),

    ("Tea & Coffee", "Robusta Dark Roast Coffee (Ca Phe Robusta)", Unit.BAG, "6.25", 4, "Bold, rich Buon Ma Thuot dark roast ground coffee (500g)."),
    ("Tea & Coffee", "Cau Dat Arabica Ground Coffee (Ca Phe Arabica)", Unit.BAG, "8.25", 4, "Delicate floral aroma and bright acidity Arabica (500g)."),
    ("Tea & Coffee", "Thai Nguyen Green Tea (Tra Xanh Tan Cuong)", Unit.PACK, "4.25", 3, "Hand-rolled curled green tea leaves from Tan Cuong (200g)."),
    ("Tea & Coffee", "Lam Dong Oolong Tea (Tra O Long)", Unit.PACK, "5.75", 3, "Smooth, fragrant lightly fermented Oolong tea spheres (250g)."),
]


CLOSED_MARKET = {
    "name": "An Dong Market",
    "address": "34-36 An Dương Vương, Phường An Đông, Thành phố Hồ Chí Minh",
    "latitude": Decimal("10.758108"),
    "longitude": Decimal("106.672182"),
    "open_time": time(6, 0),
    "close_time": time(18, 0),
    "description": "Closed for renovation. Its stalls trade at Binh Tay Market until it reopens.",
}

PENDING_FARMER_DATA = [
    {
        "email": "farmer_07@marketlink.com",
        "stall_name": "Cu Chi Green Leaf Farm",
        "contact_person": "Vo Thanh Son",
        "phone": "0901000007",
        "address": "Tỉnh lộ 8, Xã Củ Chi, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.957000"),
        "longitude": Decimal("106.508000"),
    },
    {
        "email": "farmer_08@marketlink.com",
        "stall_name": "Can Gio Coastal Produce",
        "contact_person": "Huynh Kim Ngan",
        "phone": "0901000008",
        "address": "Rừng Sác, Xã Cần Giờ, Thành phố Hồ Chí Minh",
        "latitude": Decimal("10.412000"),
        "longitude": Decimal("106.955000"),
    },
]

REVIEW_QUEUE_PRODUCTS = [
    ("Fresh Vegetables", "Curly Kale (Cai Xoan)", Unit.KG, "3.50", 0,
     "Tender curly kale grown without pesticides.", ReviewStatus.PENDING, None),
    ("Fresh Fruits", "White Flesh Dragon Fruit (Thanh Long Ruot Trang)", Unit.KG, "1.40", 2,
     "Mild, refreshing white-fleshed dragon fruit from Binh Thuan.", ReviewStatus.PENDING, None),
    ("Tea & Coffee", "Jasmine Green Tea (Tra Lai)", Unit.PACK, "4.50", 3,
     "Green tea scented with fresh jasmine flowers (200g).", ReviewStatus.PENDING, None),
    ("Spices & Condiments", "Fresh Ginger Root (Gung Tuoi)", Unit.KG, "2.20", 1,
     "Pungent young ginger, washed and trimmed.", ReviewStatus.PENDING, None),
    ("Fresh Fruits", "Used Honda Wave Motorbike", Unit.EACH, "450.00", 5,
     "2019 model, runs well, papers included.", ReviewStatus.PENDING, None),
    ("Fresh Vegetables", "Baby Spinach (Cai Bo Xoi Non)", Unit.BAG, "2.00", 1,
     "Washed baby spinach leaves (250g).", ReviewStatus.REJECTED,
     "The photo shows a different product. Please upload your own photo of this item."),
]

MARKET_IMAGE_MAP = {
    "Thu Duc Wholesale Agricultural Market": "markets/thuduc_market.jpg",
    "Hoc Mon Wholesale Market": "markets/hocmon_market.jpg",
    "Binh Dien Wholesale Market": "markets/binhdien_market.jpg",
    "Ba Chieu Market": "markets/bachieu_market.jpg",
    "Binh Tay Market (Cho Lon)": "markets/binhtay_market.jpg",
    "Tan Dinh Market": "markets/tandinh_market.jpg",
    "An Dong Market": "markets/andong_market.jpg",
}

PRODUCT_IMAGE_MAP = {
    # Fresh Vegetables
    "Water Spinach (Rau Muong)": "products/water_spinach.jpg",
    "Bok Choy (Cai Ngot)": "products/bok_choy.jpg",
    "Mustard Greens (Cai Xanh)": "products/mustard_greens.jpg",
    "Malabar Spinach (Mong Toi)": "products/malabar_spinach.jpg",
    "Red Amaranth (Rau Den)": "products/red_amaranth.jpg",
    "Green Cabbage (Bap Cai)": "products/cabbage.jpg",
    "Green Broccoli (Sup Lo Xanh)": "products/broccoli.jpg",
    "White Cauliflower (Sup Lo Trang)": "products/cauliflower.jpg",
    "Da Lat Carrots (Ca Rot)": "products/carrot.jpg",
    "Yellow Potatoes (Khoai Tay)": "products/potato.jpg",
    "Honey Sweet Potatoes (Khoai Lang Mat)": "products/sweet_potato.jpg",
    "Yellow Onions (Hanh Tay)": "products/onion.jpg",
    "Vine-Ripened Tomatoes (Ca Chua)": "products/tomato.jpg",
    "Baby Cucumbers (Dua Leo)": "products/cucumber.jpg",
    "Pumpkin (Bi Do)": "products/pumpkin.jpg",
    "Winter Melon (Bi Dao)": "products/winter_melon.jpg",
    "Sweet Luffa (Muop Huong)": "products/luffa.jpg",
    "Bottle Gourd (Trai Bau)": "products/bottle_gourd.jpg",
    "Fresh Scallions (Hanh La)": "products/scallion.jpg",
    "Bird's Eye Chillies (Ot Hiem)": "products/chilli.jpg",
    "Purple Garlic (Toi Ly Son)": "products/garlic.jpg",
    "Napa Cabbage (Cai Thao)": "products/napa_cabbage.jpg",
    "Crisp Celery (Can Tay)": "products/celery.jpg",
    "Fresh Lemongrass (Sa Cay)": "products/lemongrass.jpg",
    # Fresh Fruits
    "Red Watermelon (Dua Hau)": "products/watermelon.jpg",
    "Ri6 Durian (Sau Rieng Ri6)": "products/durian.jpg",
    "Crunchy Jackfruit (Mit Thai)": "products/jackfruit.jpg",
    "Hoa Loc Mango (Xoai Cat Hoa Loc)": "products/mango.jpg",
    "Crisp Guava (Oi Nu Hoang)": "products/guava.jpg",
    "An Phuoc Plum (Man An Phuoc)": "products/bell_fruit.jpg",
    "Cavendish Bananas (Chuoi Gia)": "products/banana.jpg",
    "Sanh Green Orange (Cam Sanh)": "products/orange.jpg",
    "Sweet Tangerines (Quyt Duong)": "products/tangerine.jpg",
    "Green-Skin Pomelo (Buoi Da Xanh)": "products/pomelo.jpg",
    "Red Flesh Dragon Fruit (Thanh Long Ruot Do)": "products/red_dragon_fruit.jpg",
    "Ripe Papaya (Du Du Chin Cay)": "products/papaya.jpg",
    "Java Rambutan (Chom Chom)": "products/rambutan.jpg",
    "Xuong Longan (Nhan Xuong)": "products/longan.jpg",
    "Thieu Lychee (Vai Thieu)": "products/lychee.jpg",
    "Da Lat Strawberries (Dau Tay)": "products/strawberry.jpg",
    "Crisp Red Apple (Tao Do)": "products/apple.jpg",
    "Fragrant Asian Pear (Le)": "products/pear.jpg",
    "Seedless Black Grapes (Nho Den)": "products/grapes.jpg",
    "Japanese Cantaloupe (Dua Luoi)": "products/cantaloupe.jpg",
    "Mangosteen (Mang Cut)": "products/mangosteen.jpg",
    "034 Avocado (Bo 034)": "products/avocado.jpg",
    "Passion Fruit (Chanh Day)": "products/passion_fruit.jpg",
    "Custard Apple (Mang Cau Ta)": "products/custard_apple.jpg",
    # Spices & Condiments
    "Natural Sea Salt (Muoi Bien)": "products/sea_salt.jpg",
    "Pure Cane Sugar (Duong Mia)": "products/cane_sugar.jpg",
    "Monosodium Glutamate MSG (Bot Ngot)": "products/msg.jpg",
    "Rich Broth Seasoning (Hat Nem)": "products/seasoning.jpg",
    "Phu Quoc Black Pepper (Tieu Den)": "products/black_pepper.jpg",
    "Pure Turmeric Powder (Tinh Bot Nghe)": "products/turmeric_powder.jpg",
    "Toasted Garlic Powder (Bot Toi)": "products/garlic_powder.jpg",
    "Sweet Onion Powder (Bot Hanh)": "products/onion_powder.jpg",
    "Smoked Chilli Powder (Bot Ot)": "products/chilli_powder.jpg",
    "Yen Bai Cinnamon Sticks (Que Cay)": "products/cinnamon.jpg",
    # Rice & Grains
    "ST25 Fragrant Jasmine Rice (Gao ST25)": "products/jasmine_rice.jpg",
    "Black Glutinous Rice (Nep Cam)": "products/black_glutinous_rice.jpg",
    "Whole Wheat Grain (Lua Mi)": "products/wheat.jpg",
    "Green Mung Beans (Dau Xanh)": "products/mung_beans.jpg",
    "Small Black Beans (Dau Den Xanh Long)": "products/black_beans.jpg",
    "Small Red Beans (Dau Do)": "products/red_beans.jpg",
    "Non-GMO Soybeans (Dau Nanh)": "products/soybeans.jpg",
    "Roasted Peanuts (Dau Phong)": "products/peanuts.jpg",
    "Binh Phuoc Roasted Cashews (Hat Dieu)": "products/cashews.jpg",
    "Dong Thap Dried Lotus Seeds (Hat Sen)": "products/lotus_seeds.jpg",
    "Roasted Watermelon Seeds (Hat Dua)": "products/watermelon_seeds.jpg",
    "Raw Pumpkin Seeds (Hat Bi)": "products/pumpkin_seeds.jpg",
    "Roasted Sunflower Seeds (Hat Huong Duong)": "products/sunflower_seeds.jpg",
    "Organic Chia Seeds (Hat Chia)": "products/chia_seeds.jpg",
    "Roasted Almonds (Hanh Nhan)": "products/almonds.jpg",
    "Shelled Walnuts (Oc Cho)": "products/walnuts.jpg",
    "Dak Lak Macadamia Nuts (Hat Macca)": "products/macadamia.jpg",
    "Roasted Chestnuts (Hat De)": "products/chestnuts.jpg",
    # Tea & Coffee
    "Robusta Dark Roast Coffee (Ca Phe Robusta)": "products/coffee_robusta.jpg",
    "Cau Dat Arabica Ground Coffee (Ca Phe Arabica)": "products/coffee_arabica.jpg",
    "Thai Nguyen Green Tea (Tra Xanh Tan Cuong)": "products/green_tea.jpg",
    "Lam Dong Oolong Tea (Tra O Long)": "products/oolong_tea.jpg",
    # Review Queue
    "Curly Kale (Cai Xoan)": "products/curly_kale.jpg",
    "White Flesh Dragon Fruit (Thanh Long Ruot Trang)": "products/white_dragon_fruit.jpg",
    "Jasmine Green Tea (Tra Lai)": "products/jasmine_tea.jpg",
    "Fresh Ginger Root (Gung Tuoi)": "products/ginger.jpg",
    "Baby Spinach (Cai Bo Xoi Non)": "products/baby_spinach.jpg",
}

HIDDEN_PRODUCT_INDEX = 26
HIDDEN_REASON = "Shoppers reported the origin on the label does not match the listing. Checking with the stall."

HISTORY_DAYS = 150
RANDOM_SEED = 20260928
PAST_OUTCOMES = [
    (OrderStatus.COMPLETED, 74),
    (OrderStatus.CANCELLED, 9),
    (OrderStatus.DECLINED, 6),
    (OrderStatus.EXPIRED, 6),
    (OrderStatus.NO_SHOW, 5),
]
REVIEW_SHARE = 0.4
AT_RISK_CUSTOMERS = 2
AT_RISK_NO_SHOW_DAYS_AGO = (4, 11, 19)

RATING_WEIGHTS = [(5, 55), (4, 30), (3, 10), (2, 5)]
PRODUCT_COMMENTS = {
    5: ["Very fresh, exactly as listed.", "Best I have bought this season.", "Great quality, will order again."],
    4: ["Good quality, a couple of pieces were small.", "Fresh and well packed.", "Tasty, a little pricier than the market floor."],
    3: ["Okay, but not as ripe as I hoped.", "Fine for cooking, not the freshest batch."],
    2: ["Some pieces were bruised.", "Smaller than the photo suggested."],
}
FARMER_COMMENTS = {
    5: ["Order was ready the moment I arrived.", "Friendly stall, packed everything carefully."],
    4: ["Quick pickup after a short wait.", "Helpful and polite."],
    3: ["Had to wait about ten minutes for my bag."],
    2: ["The stall was hard to find and my order was not ready."],
}
REPLIES = ["Thank you for shopping with us!", "Thanks, see you next market day.", None, None]


@contextmanager
def keep_given_timestamps(*models):
    """Let the seed set created_at/updated_at itself instead of auto_now stamping "now".

    The admin dashboard counts orders by created_at, so history seeded at one instant would
    all land on the day the command ran.
    """
    fields = [
        field
        for model in models
        for field in model._meta.concrete_fields
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    ]
    saved = [(field, field.auto_now, field.auto_now_add) for field in fields]
    for field in fields:
        field.auto_now = field.auto_now_add = False
    try:
        yield
    finally:
        for field, auto_now, auto_now_add in saved:
            field.auto_now, field.auto_now_add = auto_now, auto_now_add


class Command(BaseCommand):
    help = "Wipes old sample data cleanly, resets auto-increment IDs to 1, and seeds real production-grade data."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting complete cleanup and database reset..."))

        self._wipe_and_reset_database()
        self.stdout.write(self.style.SUCCESS("[OK] All business tables truncated & auto-increment IDs reset to 1."))

        with transaction.atomic():
            admin_user = self._seed_admin()
            markets = self._seed_markets()
            categories = self._seed_categories()
            self._seed_price_guidelines(categories)
            farmers = self._seed_farmers(markets)
            products = self._seed_products(categories, farmers)
            customers = self._seed_customers()
            self.rng = random.Random(RANDOM_SEED)
            order_count = self._seed_sample_orders_and_reviews(customers, farmers, markets, products)
            closed_market = self._seed_closed_market()
            pending_farmers = self._seed_pending_farmers()
            queue = self._seed_review_queue(categories, farmers, products, admin_user)
            follow_up = scan_existing()

        self.stdout.write(self.style.SUCCESS("\n========================================================"))
        self.stdout.write(self.style.SUCCESS("REAL DATA SEEDING COMPLETE WITH AUTO-INCREMENT IDs = 1"))
        self.stdout.write(self.style.SUCCESS("========================================================"))
        self.stdout.write(f"  Superuser / Admin : admin@marketlink.com / {DEFAULT_PASSWORD}")
        self.stdout.write(f"  Markets           : {len(markets)} markets in HCMC (IDs 1 to {len(markets)})")
        self.stdout.write(f"  Categories        : {len(categories)} categories (IDs 1 to {len(categories)})")
        self.stdout.write(f"  Farmers           : {len(farmers)} farmers with stalls & slots (IDs 2 to {len(farmers) + 1})")
        self.stdout.write(f"  Products          : {len(products)} products across 5 categories (IDs 1 to {len(products)})")
        self.stdout.write(f"  Customers         : {len(customers)} customers (IDs 8 to 27), {AT_RISK_CUSTOMERS} at risk")
        self.stdout.write(f"  Orders            : {order_count} over the last {HISTORY_DAYS} days and the coming week")
        self.stdout.write(f"  Closed market     : {closed_market.name}")
        self.stdout.write(f"  Pending farmers   : {len(pending_farmers)}")
        self.stdout.write(
            f"  Review queue      : {queue['pending']} pending, {queue['rejected']} rejected, 1 hidden product"
        )
        self.stdout.write(
            f"  Follow-up queue   : {follow_up['reviews'] + follow_up['replies']} review(s), "
            f"{follow_up['products']} product(s), {follow_up['customers']} shopper(s) flagged automatically"
        )
        self.stdout.write("  AI listing review : run `python manage.py ai_review_pending` to review the pending listings")
        self.stdout.write(f"  All Passwords     : '{DEFAULT_PASSWORD}'")
        self.stdout.write(self.style.SUCCESS("========================================================\n"))

    def _wipe_and_reset_database(self):
        """Truncate all application business tables in MySQL with foreign key checks disabled.
        TRUNCATE TABLE in MySQL automatically resets the AUTO_INCREMENT counter to 1.
        """
        tables = [
            "farmer_reviews",
            "product_reviews",
            "product_ai_reviews",
            "order_status_history",
            "order_item_histories",
            "order_items",
            "order_histories",
            "orders",
            "pickup_slot_histories",
            "pickup_slots",
            "product_markets",
            "farmer_market_histories",
            "farmer_markets",
            "farmer_closure_histories",
            "farmer_closures",
            "market_closures",
            "market_operating_days",
            "products",
            "product_histories",
            "price_guidelines",
            "categories",
            "markets",
            "favorite_farmers",
            "favorite_markets",
            "favorite_products",
            "moderation_flags",
            "notifications",
            "announcements",
            "audit_logs",
            "customer_profile_histories",
            "customer_profiles",
            "farmer_profile_histories",
            "farmer_profiles",
            "users_groups",
            "users_user_permissions",
            "django_admin_log",
            "django_session",
            "users",
        ]
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE `{table}`;")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    def _seed_admin(self):
        role_admin = Role.objects.get(code=RoleCode.ADMIN)
        admin = CustomUser.objects.create(
            id=1,
            email="admin@marketlink.com",
            password=make_password(DEFAULT_PASSWORD),
            role=role_admin,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        return admin

    def _seed_markets(self):
        markets = []
        for idx, item in enumerate(MARKET_DATA, start=1):
            m = Market.objects.create(
                id=idx,
                name=item["name"],
                address=item["address"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                open_time=item["open_time"],
                close_time=item["close_time"],
                description=item["description"],
                image=MARKET_IMAGE_MAP.get(item["name"]),
                map_provider="OSM",
                is_active=True,
            )
            for day in range(1, 8):
                MarketOperatingDay.objects.create(market=m, day_of_week=day)
            markets.append(m)
        return markets

    def _seed_categories(self):
        categories = {}
        for name, icon, order in CATEGORY_DATA:
            cat = Category.objects.create(
                id=order,
                name=name,
                icon=icon,
                display_order=order,
                is_active=True,
            )
            categories[name] = cat
        return categories

    def _seed_price_guidelines(self, categories):
        PriceGuideline.objects.bulk_create(
            [
                PriceGuideline(
                    category=categories[category_name],
                    unit=unit,
                    min_price=Decimal(low),
                    max_price=Decimal(high),
                    max_stock=max_stock,
                )
                for category_name, units in PRICE_GUIDELINES.items()
                for unit, (low, high, max_stock) in units.items()
            ]
        )

    def _link(self, product, *stalls):
        ProductMarket.objects.bulk_create(
            [ProductMarket(product=product, farmer_market=stall) for stall in stalls]
        )

    def _seed_farmers(self, markets):
        role_farmer = Role.objects.get(code=RoleCode.FARMER)
        farmers = []
        self.home_stalls = {}
        self.weekend_stalls = {}
        for idx, data in enumerate(FARMER_DATA, start=2):
            user = CustomUser.objects.create(
                id=idx,
                email=data["email"],
                password=make_password(DEFAULT_PASSWORD),
                role=role_farmer,
                is_active=True,
            )
            market = markets[data["market_idx"]]
            profile = FarmerProfile.objects.create(
                user=user,
                stall_name=data["stall_name"],
                contact_person=data["contact_person"],
                phone=data["phone"],
                address=market.address,
                latitude=market.latitude,
                longitude=market.longitude,
                status=FarmerStatus.APPROVED,
                operating_days=[1, 2, 3, 4, 5, 6, 7],
                order_cutoff_hours=12,
            )
            fm = FarmerMarket.objects.create(
                farmer=profile,
                market=market,
                stall_label=data["stall_label"],
            )
            self.home_stalls[profile.pk] = fm
            weekend_market = markets[(data["market_idx"] + 1) % len(markets)]
            weekend = FarmerMarket.objects.create(
                farmer=profile,
                market=weekend_market,
                stall_label=f"Weekend row, Stall {idx:02d}",
            )
            self.weekend_stalls[profile.pk] = weekend
            for day in (DayOfWeek.SATURDAY, DayOfWeek.SUNDAY):
                PickupSlot.objects.create(
                    farmer_market=weekend,
                    day_of_week=day,
                    start_time=time(6, 0),
                    end_time=time(9, 0),
                    is_active=True,
                )
            for day in range(1, 8):
                PickupSlot.objects.create(
                    farmer_market=fm,
                    day_of_week=day,
                    start_time=time(6, 0),
                    end_time=time(9, 0),
                    is_active=True,
                )
                PickupSlot.objects.create(
                    farmer_market=fm,
                    day_of_week=day,
                    start_time=time(9, 0),
                    end_time=time(11, 0),
                    is_active=True,
                )
            farmers.append(profile)
        return farmers

    def _seed_products(self, categories, farmers):
        products = []
        for idx, (cat_name, prod_name, unit, price, farmer_idx, desc) in enumerate(PRODUCTS_DATA, start=1):
            category = categories[cat_name]
            farmer = farmers[farmer_idx]
            p = Product.objects.create(
                id=idx,
                farmer=farmer,
                category=category,
                name=prod_name,
                description=desc,
                image=PRODUCT_IMAGE_MAP.get(prod_name),
                price=Decimal(price),
                unit=unit,
                stock_quantity=100,
                weekly_default_quantity=150,
                min_per_order=1,
                max_per_order=20,
                is_available=True,
                is_archived=False,
                review_status=ReviewStatus.APPROVED,
            )
            if idx % 2 == 0:
                self._link(p, self.home_stalls[farmer.pk], self.weekend_stalls[farmer.pk])
            else:
                self._link(p, self.home_stalls[farmer.pk])
            products.append(p)
        return products

    def _seed_customers(self):
        role_customer = Role.objects.get(code=RoleCode.CUSTOMER)
        customers = []
        for idx in range(1, 21):
            user_id = idx + 7
            user = CustomUser.objects.create(
                id=user_id,
                email=f"customer_{idx:02d}@marketlink.com",
                password=make_password(DEFAULT_PASSWORD),
                role=role_customer,
                is_active=True,
            )
            name = CUSTOMER_NAMES[idx - 1]
            address = CUSTOMER_ADDRESSES[idx - 1]
            phone = f"0981000{idx:03d}"
            CustomerProfile.objects.create(
                user=user,
                full_name=name,
                phone=phone,
                address=address,
            )
            customers.append(user)
        return customers

    def _seed_sample_orders_and_reviews(self, customers, farmers, markets, products):
        """Hand-written showcase orders, months of history, at-risk shoppers and open orders.

        Specs are built first and created oldest first, so order numbers follow the dates.
        Returns the number of orders created.
        """
        today = timezone.localdate()
        by_farmer = defaultdict(list)
        for product in products:
            by_farmer[product.farmer_id].append(product)
        self.slots = defaultdict(list)
        home_stall_ids = [stall.pk for stall in self.home_stalls.values()]
        for slot in (
            PickupSlot.objects.select_related("farmer_market__market")
            .filter(farmer_market_id__in=home_stall_ids)
            .order_by("start_time")
        ):
            self.slots[(slot.farmer_market.farmer_id, slot.day_of_week)].append(slot)

        specs = self._showcase_specs(customers, farmers, products, today)
        specs += self._history_specs(customers, farmers, by_farmer, today)
        specs += self._at_risk_specs(customers, farmers, by_farmer, today)
        specs += self._open_specs(customers, farmers, by_farmer, today)
        specs.sort(key=lambda spec: spec["created_at"])

        with keep_given_timestamps(Order, OrderItem, OrderStatusHistory, ProductReview, FarmerReview):
            trail = []
            for spec in specs:
                trail += self._create_order(spec)
            OrderStatusHistory.objects.bulk_create(trail)
        return len(specs)


    def _spec(self, *, customer, farmer, pickup_d, status, lines, note=None, review=None, slot_index=0, placed_hours_before=None):
        slots = self.slots[(farmer.pk, pickup_d.isoweekday())]
        slot = slots[min(slot_index, len(slots) - 1)]
        start = timezone.make_aware(datetime.combine(pickup_d, slot.start_time))
        cutoff = start - timedelta(hours=farmer.order_cutoff_hours)
        if placed_hours_before is None:
            placed_hours_before = self.rng.randint(farmer.order_cutoff_hours + 1, 72)
        created_at = start - timedelta(hours=placed_hours_before, minutes=self.rng.randint(0, 59))
        created_at = min(created_at, cutoff - timedelta(minutes=5), timezone.now() - timedelta(minutes=5))
        return {
            "customer": customer,
            "farmer": farmer,
            "slot": slot,
            "pickup_d": pickup_d,
            "status": status,
            "lines": lines,
            "note": note,
            "review": review,
            "created_at": created_at,
        }

    def _random_lines(self, farmer_products):
        picked = self.rng.sample(farmer_products, k=min(len(farmer_products), self.rng.randint(1, 3)))
        return [(product, self.rng.randint(1, min(4, product.max_per_order or 4))) for product in picked]

    def _pick(self, weighted):
        values, weights = zip(*weighted)
        return self.rng.choices(values, weights=weights, k=1)[0]

    def _showcase_specs(self, customers, farmers, products, today):
        """The six hand-written orders, kept for demos that point at them."""
        rows = [
            {
                "customer": customers[0],
                "farmer": farmers[3],
                "status": OrderStatus.COMPLETED,
                "note": "Please pick the ripest tomatoes for me.",
                "days_ago": 3,
                "lines": [(products[10], 2), (products[12], 3)],
                "review": {
                    "product_rating": 5,
                    "product_comment": "Super fresh tomatoes and sweet potatoes, taste wonderful!",
                    "farmer_rating": 5,
                    "farmer_comment": "The stall owner was very friendly and packed my goods carefully.",
                    "reply": "Thank you so much! We are glad you enjoyed them.",
                },
            },
            {
                "customer": customers[1],
                "farmer": farmers[4],
                "status": OrderStatus.COMPLETED,
                "note": "Standard packaging is fine.",
                "days_ago": 1,
                "lines": [(products[48], 1), (products[58], 2)],
                "review": {
                    "product_rating": 4,
                    "product_comment": "Aromatic pepper and crispy cashews. Will buy again.",
                    "farmer_rating": 5,
                    "farmer_comment": "Fast pickup service at the market.",
                    "reply": "Thank you for shopping with Cho Lon Spices!",
                },
            },
            {
                "customer": customers[0],
                "farmer": farmers[0],
                "status": OrderStatus.ACCEPTED,
                "note": "I will arrive around 8:00 AM.",
                "days_ago": -2,
                "lines": [(products[0], 2), (products[1], 2)],
            },
            {
                "customer": customers[2],
                "farmer": farmers[5],
                "status": OrderStatus.READY_FOR_PICKUP,
                "note": "Calling ahead before pickup.",
                "days_ago": 0,
                "slot_index": 1,
                "lines": [(products[39], 1), (products[41], 1)],
            },
            {
                "customer": customers[3],
                "farmer": farmers[1],
                "status": OrderStatus.PLACED,
                "note": "First time ordering online.",
                "days_ago": -2,
                "lines": [(products[5], 2), (products[8], 1)],
            },
            {
                "customer": customers[4],
                "farmer": farmers[2],
                "status": OrderStatus.CANCELLED,
                "note": "Sorry, I had an unexpected schedule change.",
                "days_ago": 2,
                "lines": [(products[24], 1)],
            },
            {
                "customer": customers[5],
                "farmer": farmers[3],
                "status": OrderStatus.COMPLETED,
                "note": None,
                "days_ago": 5,
                "lines": [(products[12], 2)],
                "review": {
                    "product_rating": 2,
                    "product_comment": "Tomatoes were fine, but order direct at www.cheaptomatoes.example and save 30%.",
                    "farmer_rating": 3,
                    "farmer_comment": "Pickup was a bit slow.",
                },
            },
            {
                "customer": customers[6],
                "farmer": farmers[0],
                "status": OrderStatus.COMPLETED,
                "note": None,
                "days_ago": 6,
                "lines": [(products[0], 3)],
                "review": {
                    "product_rating": 5,
                    "product_comment": "Fresh greens! Zalo me on 0909 123 456, I resell them cheaper.",
                    "farmer_rating": 5,
                    "farmer_comment": "Quick pickup.",
                },
            },
            *[
                {
                    "customer": customers[7 + index],
                    "farmer": farmers[2],
                    "status": OrderStatus.COMPLETED,
                    "note": None,
                    "days_ago": days_ago,
                    "lines": [(products[27], 2)],
                    "review": {
                        "product_rating": rating,
                        "product_comment": comment,
                        "farmer_rating": 3,
                        "farmer_comment": "Pickup was fine.",
                    },
                }
                for index, (days_ago, rating, comment) in enumerate(
                    [
                        (16, 2, "Sour and much smaller than the photo."),
                        (9, 1, "These are not Hoa Loc mangoes at all. Not as described."),
                        (3, 2, "Half of them were overripe and bruised."),
                    ]
                )
            ],
        ]
        return [
            self._spec(
                customer=row["customer"],
                farmer=row["farmer"],
                pickup_d=today - timedelta(days=row["days_ago"]),
                status=row["status"],
                lines=row["lines"],
                note=row["note"],
                review=row.get("review"),
                slot_index=row.get("slot_index", 0),
                placed_hours_before=20,
            )
            for row in rows
        ]

    def _history_specs(self, customers, farmers, by_farmer, today):
        """Past pickups, growing from about one a day to four as the platform catches on."""
        specs = []
        for offset in range(HISTORY_DAYS, 0, -1):
            pickup_d = today - timedelta(days=offset)
            grown = 1 + (HISTORY_DAYS - offset) * 3 // HISTORY_DAYS
            weekend = 1 if pickup_d.isoweekday() >= DayOfWeek.SATURDAY else 0
            for _ in range(max(0, grown + weekend + self.rng.randint(-1, 1))):
                farmer = self.rng.choice(farmers)
                specs.append(
                    self._spec(
                        customer=self.rng.choice(customers),
                        farmer=farmer,
                        pickup_d=pickup_d,
                        status=self._pick(PAST_OUTCOMES),
                        lines=self._random_lines(by_farmer[farmer.pk]),
                        slot_index=self.rng.randint(0, 1),
                    )
                )
        return specs

    def _at_risk_specs(self, customers, farmers, by_farmer, today):
        """Three no-shows in the last 30 days for the last customers: "Shoppers at risk"."""
        specs = []
        for customer in customers[-AT_RISK_CUSTOMERS:]:
            for days_ago in AT_RISK_NO_SHOW_DAYS_AGO:
                farmer = self.rng.choice(farmers)
                specs.append(
                    self._spec(
                        customer=customer,
                        farmer=farmer,
                        pickup_d=today - timedelta(days=days_ago),
                        status=OrderStatus.NO_SHOW,
                        lines=self._random_lines(by_farmer[farmer.pk]),
                    )
                )
        return specs

    def _open_specs(self, customers, farmers, by_farmer, today):
        """Orders still waiting for pickup in the coming days.

        Two days ahead at the earliest, so no cutoff has passed whenever the seed runs.
        """
        specs = []
        for ahead in range(2, 7):
            for _ in range(self.rng.randint(2, 4)):
                farmer = self.rng.choice(farmers)
                specs.append(
                    self._spec(
                        customer=self.rng.choice(customers[:-AT_RISK_CUSTOMERS]),
                        farmer=farmer,
                        pickup_d=today + timedelta(days=ahead),
                        status=self._pick([(OrderStatus.PLACED, 2), (OrderStatus.ACCEPTED, 1)]),
                        lines=self._random_lines(by_farmer[farmer.pk]),
                        placed_hours_before=self.rng.randint(49, 80) + ahead * 12,
                    )
                )
        return specs


    def _create_order(self, spec):
        """Create the order, its lines and any review. Returns its status rows, unsaved."""
        farmer, slot = spec["farmer"], spec["slot"]
        farmer_market = slot.farmer_market
        start = timezone.make_aware(datetime.combine(spec["pickup_d"], slot.start_time))
        end = timezone.make_aware(datetime.combine(spec["pickup_d"], slot.end_time))
        cutoff = start - timedelta(hours=farmer.order_cutoff_hours)
        steps = self._status_steps(spec["status"], spec["created_at"], start, end, cutoff)
        last_change = steps[-1][4]

        order = Order.objects.create(
            customer=spec["customer"],
            farmer=farmer,
            market=farmer_market.market,
            pickup_slot=slot,
            stall_label=farmer_market.stall_label,
            pickup_date=spec["pickup_d"],
            pickup_start_at=start,
            pickup_end_at=end,
            cutoff_at=cutoff,
            status=spec["status"],
            note=spec["note"],
            total_amount=sum(product.price * qty for product, qty in spec["lines"]),
            version=len(steps),
            created_at=spec["created_at"],
            updated_at=last_change,
        )
        items = OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=product,
                    product_name=product.name,
                    unit=product.unit,
                    unit_price=product.price,
                    quantity=qty,
                    line_total=product.price * qty,
                    created_at=spec["created_at"],
                    updated_at=spec["created_at"],
                )
                for product, qty in spec["lines"]
            ]
        )

        actors = {
            ActorRole.CUSTOMER: spec["customer"],
            ActorRole.FARMER: farmer.user,
            ActorRole.SYSTEM: None,
        }
        trail = [
            OrderStatusHistory(
                order=order,
                from_status=from_status,
                to_status=to_status,
                transition=transition,
                actor=actors[role],
                actor_role=role,
                change_reason=ChangeReason.SYSTEM_EXPIRED if transition == Transition.T8 else None,
                created_at=at,
            )
            for from_status, to_status, transition, role, at in steps
        ]

        if spec["status"] == OrderStatus.COMPLETED:
            review = spec["review"]
            if review is None and self.rng.random() < REVIEW_SHARE:
                review = self._random_review()
            if review is not None:
                first_item = OrderItem.objects.filter(order=order).order_by("id").first() if items else None
                self._create_reviews(order, first_item, review, end)
        return trail

    def _status_steps(self, status, placed, start, end, cutoff):
        """(from, to, transition, actor role, when) for every change that led to ``status``."""
        now = timezone.now()
        accepted = min(placed + timedelta(hours=self.rng.randint(1, 5)), cutoff)
        steps = [("", OrderStatus.PLACED, Transition.T1, ActorRole.CUSTOMER, placed)]
        if status in (OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP, OrderStatus.COMPLETED, OrderStatus.NO_SHOW):
            steps.append((OrderStatus.PLACED, OrderStatus.ACCEPTED, Transition.T2, ActorRole.FARMER, accepted))
        if status in (OrderStatus.READY_FOR_PICKUP, OrderStatus.COMPLETED, OrderStatus.NO_SHOW):
            steps.append(
                (OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP, Transition.T9, ActorRole.FARMER, start - timedelta(minutes=30))
            )
        if status == OrderStatus.COMPLETED:
            steps.append(
                (OrderStatus.READY_FOR_PICKUP, OrderStatus.COMPLETED, Transition.T10, ActorRole.FARMER,
                 start + timedelta(minutes=self.rng.randint(10, 100)))
            )
        elif status == OrderStatus.NO_SHOW:
            steps.append(
                (OrderStatus.READY_FOR_PICKUP, OrderStatus.NO_SHOW, Transition.T11, ActorRole.FARMER, end + timedelta(minutes=15))
            )
        elif status == OrderStatus.CANCELLED:
            steps.append(
                (OrderStatus.PLACED, OrderStatus.CANCELLED, Transition.T5, ActorRole.CUSTOMER,
                 min(placed + timedelta(hours=self.rng.randint(1, 6)), cutoff))
            )
        elif status == OrderStatus.DECLINED:
            steps.append((OrderStatus.PLACED, OrderStatus.DECLINED, Transition.T3, ActorRole.FARMER, accepted))
        elif status == OrderStatus.EXPIRED:
            steps.append((OrderStatus.PLACED, OrderStatus.EXPIRED, Transition.T8, ActorRole.SYSTEM, cutoff))
        return [(f, t, tr, role, min(at, now)) for f, t, tr, role, at in steps]

    def _random_review(self):
        product_rating = self._pick(RATING_WEIGHTS)
        farmer_rating = max(2, min(5, product_rating + self.rng.choice([-1, 0, 0, 1])))
        return {
            "product_rating": product_rating,
            "product_comment": self.rng.choice(PRODUCT_COMMENTS[product_rating]),
            "farmer_rating": farmer_rating,
            "farmer_comment": self.rng.choice(FARMER_COMMENTS[farmer_rating]),
            "reply": self.rng.choice(REPLIES),
        }

    def _create_reviews(self, order, first_item, review, pickup_end):
        now = timezone.now()
        written = min(pickup_end + timedelta(hours=self.rng.randint(2, 30)), now)
        replied = min(written + timedelta(hours=self.rng.randint(1, 20)), now) if review.get("reply") else None
        common = {
            "reply": review.get("reply"),
            "replied_at": replied,
            "created_at": written,
            "updated_at": replied or written,
        }
        if first_item is not None:
            ProductReview.objects.create(
                order_item=first_item,
                rating=review["product_rating"],
                comment=review["product_comment"],
                **common,
            )
        FarmerReview.objects.create(
            order=order,
            rating=review["farmer_rating"],
            comment=review["farmer_comment"],
            **common,
        )


    def _seed_closed_market(self):
        market = Market.objects.create(
            map_provider="OSM",
            is_active=False,
            image=MARKET_IMAGE_MAP.get(CLOSED_MARKET["name"]),
            **CLOSED_MARKET,
        )
        for day in range(1, 8):
            MarketOperatingDay.objects.create(market=market, day_of_week=day)
        return market

    def _seed_pending_farmers(self):
        role_farmer = Role.objects.get(code=RoleCode.FARMER)
        profiles = []
        for data in PENDING_FARMER_DATA:
            user = CustomUser.objects.create(
                email=data["email"],
                password=make_password(DEFAULT_PASSWORD),
                role=role_farmer,
                is_active=True,
            )
            profiles.append(
                FarmerProfile.objects.create(
                    user=user,
                    stall_name=data["stall_name"],
                    contact_person=data["contact_person"],
                    phone=data["phone"],
                    address=data["address"],
                    latitude=data["latitude"],
                    longitude=data["longitude"],
                    status=FarmerStatus.PENDING,
                    operating_days=[1, 2, 3, 4, 5, 6, 7],
                    order_cutoff_hours=12,
                )
            )
        return profiles

    def _seed_review_queue(self, categories, farmers, products, admin_user):
        now = timezone.now()
        counts = {"pending": 0, "rejected": 0}
        for cat_name, name, unit, price, farmer_idx, desc, status, note in REVIEW_QUEUE_PRODUCTS:
            reviewed = status != ReviewStatus.PENDING
            queued = Product.objects.create(
                farmer=farmers[farmer_idx],
                category=categories[cat_name],
                name=name,
                description=desc,
                image=PRODUCT_IMAGE_MAP.get(name),
                price=Decimal(price),
                unit=unit,
                stock_quantity=50,
                weekly_default_quantity=50,
                min_per_order=1,
                max_per_order=10,
                is_available=True,
                review_status=status,
                review_note=note,
                reviewed_at=now if reviewed else None,
                reviewed_by=admin_user if reviewed else None,
            )
            self._link(queued, self.home_stalls[queued.farmer_id])
            counts["pending" if status == ReviewStatus.PENDING else "rejected"] += 1

        hidden = products[HIDDEN_PRODUCT_INDEX]
        hidden.is_hidden_by_admin = True
        hidden.moderation_action = ModerationAction.HIDE
        hidden.hidden_reason = HIDDEN_REASON
        hidden.hidden_at = now
        hidden.hidden_by = admin_user
        hidden.save(
            update_fields=[
                "is_hidden_by_admin",
                "moderation_action",
                "hidden_reason",
                "hidden_at",
                "hidden_by",
                "updated_at",
            ]
        )
        return counts
