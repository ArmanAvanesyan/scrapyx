from pydantic import BaseModel, Field

class SpiderCompletionEvent(BaseModel):
    """Spider completion event model."""
    job_id: str = Field(..., description="Scrapyd job ID")
    spider_name: str = Field(..., description="Spider name")
    status: str = Field(..., description="success or failed")
    reason: str = Field(..., description="Completion reason")
    items_count: int = Field(default=0, description="Number of items scraped")
    errors_count: int = Field(default=0, description="Number of errors")
    project: str = Field(..., description="Scrapyd project name")

class WebhookCallbackEvent(BaseModel):
    """Webhook callback event model."""
    task_id: str = Field(..., description="Task ID")
    callback_url: str = Field(..., description="Webhook URL")
    status: str = Field(..., description="Task status")
    data: dict = Field(..., description="Task result data")

