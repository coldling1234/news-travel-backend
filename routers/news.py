from fastapi import APIRouter, Depends, Query, HTTPException
from crud import news
from sqlalchemy.ext.asyncio import AsyncSession
from config.db_conf import get_db

#创建API实例
router = APIRouter(prefix="/api/news", tags=["news"])

@router.get("/categories")
async def get_categories(skip: int = 0, limit: int = 100,db: AsyncSession = Depends(get_db)):

    categories = await news.get_categories(db,skip, limit)
    return {
        "code":200,
        "message":"获取新闻分类成功",
        "data": categories
    }

@router.get("/list")
async def get_news_list(
        category_id: int = Query(...,alias="categoryId"),
        page: int = 1,
        page_size: int = Query(10,alias="pageSize",le=100),
        db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size
    news_list = await news.get_news_list(db,category_id,offset,page_size)
    total = await news.get_news_count(db,category_id)
    has_more = (offset + len(news_list)) < total
    return {
        "code":200,
        "message":"获取新闻列表成功",
        "data":{
            "list":news_list,
            "total":total,
            "hasMore":has_more
        }
    }

@router.get("/detail")
async def get_news_detail(news_id:int = Query(...,alias="id"),db: AsyncSession = Depends(get_db)):

    news_datail = await news.get_news_detail(db,news_id)
    if not news_datail:
        raise HTTPException(status_code=404,detail="新闻不存在")

    await news.increase_news_views(db,news_datail.id)

    related_news = await news.get_related_news(db,news_datail.id,news_datail.category_id)

    return {
        "code": 200,
        "message": "获取新闻详情成功",
        "data": {
            "id":news_datail.id,
            "title":news_datail.title,
            "content":news_datail.content,
            "image":news_datail.image,
            "author":news_datail.author,
            "publishTime":news_datail.publish_time,
            "categoryId":news_datail.category_id,
            "views":news_datail.views,
            "relatedNews":related_news
        }
    }