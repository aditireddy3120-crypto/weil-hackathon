use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

use weil_rs::ai::agents::base::BaseAgentHelper;
use weil_rs::ai::agents::models::Model;
use weil_rs::runtime::Runtime;

use weil_macros::WeilType;
use weil_macros::{smart_contract, constructor, query, mutate};

#[derive(Serialize, Deserialize, WeilType)]
pub struct DropshippingStepAgentContract {
    mcp_contract_addresses: Vec<String>,
}
#[smart_contract]
impl DropshippingStepAgentContract {

    #[constructor]
    pub fn init() -> Self {
        Self {
        mcp_contract_addresses: vec![],
      }
    }
    

    #[query]
    pub fn run(
        &self,
        _namespace: String,
        _flow_id: String,
        execution_context: ExecutionContext
    ) -> (RunStatus, ExecutionContext) {

        let state = DropshippingStepAgentContractState::new(
            self.mcp_contract_addresses.clone()
        );

        state.run(execution_context)
    }

    #[query]
    pub fn resume(
        &self,
        _namespace: String,
        _flow_id: String
    ) -> (RunStatus, ExecutionContext) {

        let ctx = ExecutionContext {
            step: None,
            answers: vec![],
            prompt_plan: PromptPlan { prompts: BTreeMap::new() },
            model: Model::GPT_5POINT1,
            model_key: None,
            context: BTreeMap::new(),
        };

        (RunStatus::Continue, ctx)
    }

    #[query]
    pub fn get_context(
        &self,
        _namespace: String,
        _flow_id: String
    ) -> ExecutionContext {

        ExecutionContext {
            step: None,
            answers: vec![],
            prompt_plan: PromptPlan { prompts: BTreeMap::new() },
            model: Model::GPT_5POINT1,
            model_key: None,
            context: BTreeMap::new(),
        }
    }

    #[mutate]
    pub fn attach_context(
        &mut self,
        _namespace: String,
        _flow_id: String,
        key: String,
        value: String
    ) -> String {

        format!("attached {}={}", key, value)
    }
}

// These names should match the names registered in your environment / other applets.
const BASE_AGENT_HELPER_NAME: &str = "BASE_AGENT_HELPER";

// Steps in the dropshipping flow.
#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd, Serialize, Deserialize)]
pub enum Step {
    CartReview,
    RiskCheck,
    HumanApproval,
    PayWithWUSD,
    PlaceSupplierOrder,
    FulfillmentUpdate,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum RunStatus {
    Continue,
    Failed,
    Pending,
    Done,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PromptPlan {
    pub prompts: BTreeMap<Step, String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExecutionContext {
    pub step: Option<Step>,
    pub answers: Vec<String>,
    pub prompt_plan: PromptPlan,
    pub model: Model,
    pub model_key: Option<String>,
    pub context: BTreeMap<String, String>,
}

pub(crate) trait State: Send + Sync {
    fn name(&self) -> Step;

    fn do_work(
        &self,
        mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus);
}

// --- Individual step handlers ---

pub(crate) struct CartReviewState;

impl State for CartReviewState {
    fn name(&self) -> Step {
        Step::CartReview
    }

    fn do_work(
        &self,
        mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus) {
        if let Some(prompt) = ctx.prompt_plan.prompts.get(&self.name()) {
            let base_agent_helper_address =
                Runtime::contract_id_for_name(BASE_AGENT_HELPER_NAME).unwrap();
            let helper = BaseAgentHelper::new(base_agent_helper_address);

            let res = helper.run_task(
                prompt.clone(),
                mcp_addresses
                    .get(0)
                    .cloned()
                    .unwrap_or_default(), // e.g. catalog MCP
                ctx.model.clone(),
                None,
            );

            match res {
                Ok(r) => ctx.answers.push(r),
                Err(e) => {
                    ctx.answers
                        .push(format!("Cart review failed: {e}"));
                    return (None, RunStatus::Failed);
                }
            }
        }

        (Some(Step::RiskCheck), RunStatus::Continue)
    }
}

pub(crate) struct RiskCheckState;

impl State for RiskCheckState {
    fn name(&self) -> Step {
        Step::RiskCheck
    }

    fn do_work(
        &self,
        mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus) {
        if let Some(prompt) = ctx.prompt_plan.prompts.get(&self.name()) {
            let base_agent_helper_address =
                Runtime::contract_id_for_name(BASE_AGENT_HELPER_NAME).unwrap();
            let helper = BaseAgentHelper::new(base_agent_helper_address);

            let res = helper.run_task(
                prompt.clone(),
                mcp_addresses
                    .get(1)
                    .cloned()
                    .unwrap_or_else(|| mcp_addresses.get(0).cloned().unwrap_or_default()),
                ctx.model.clone(),
                None,
            );

            match res {
                Ok(r) => ctx.answers.push(r),
                Err(e) => {
                    ctx.answers
                        .push(format!("Risk check failed: {e}"));
                    return (None, RunStatus::Failed);
                }
            }
        }

        (Some(Step::HumanApproval), RunStatus::Continue)
    }
}

pub(crate) struct HumanApprovalState;

impl State for HumanApprovalState {
    fn name(&self) -> Step {
        Step::HumanApproval
    }

    fn do_work(
        &self,
        _mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus) {
        ctx.answers
            .push("awaiting human approval for this order".to_string());
        ctx.step = Some(Step::PayWithWUSD);
        (Some(Step::PayWithWUSD), RunStatus::Pending)
    }
}

pub(crate) struct PayWithWusdState;

impl State for PayWithWusdState {
    fn name(&self) -> Step {
        Step::PayWithWUSD
    }

    fn do_work(
        &self,
        mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus) {
        if let Some(approval) = ctx.context.get("approval") {
            if approval != "approved" {
                ctx.answers
                    .push("order rejected by human reviewer".to_string());
                return (None, RunStatus::Failed);
            }
        } else {
            ctx.answers
                .push("no approval found in context".to_string());
            return (None, RunStatus::Failed);
        }

        if let Some(prompt) = ctx.prompt_plan.prompts.get(&self.name()) {
            let base_agent_helper_address =
                Runtime::contract_id_for_name(BASE_AGENT_HELPER_NAME).unwrap();
            let helper = BaseAgentHelper::new(base_agent_helper_address);

            let res = helper.run_task(
                prompt.clone(),
                mcp_addresses
                    .get(2)
                    .cloned()
                    .unwrap_or_else(|| mcp_addresses.get(0).cloned().unwrap_or_default()),
                ctx.model.clone(),
                None,
            );

            match res {
                Ok(r) => ctx.answers.push(r),
                Err(e) => {
                    ctx.answers
                        .push(format!("WUSD payment failed: {e}"));
                    return (None, RunStatus::Failed);
                }
            }
        }

        (Some(Step::PlaceSupplierOrder), RunStatus::Continue)
    }
}

pub(crate) struct PlaceSupplierOrderState;

impl State for PlaceSupplierOrderState {
    fn name(&self) -> Step {
        Step::PlaceSupplierOrder
    }

    fn do_work(
        &self,
        mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus) {
        if let Some(prompt) = ctx.prompt_plan.prompts.get(&self.name()) {
            let base_agent_helper_address =
                Runtime::contract_id_for_name(BASE_AGENT_HELPER_NAME).unwrap();
            let helper = BaseAgentHelper::new(base_agent_helper_address);

            let res = helper.run_task(
                prompt.clone(),
                mcp_addresses
                    .get(3)
                    .cloned()
                    .unwrap_or_else(|| mcp_addresses.get(0).cloned().unwrap_or_default()),
                ctx.model.clone(),
                None,
            );

            match res {
                Ok(r) => ctx.answers.push(r),
                Err(e) => {
                    ctx.answers
                        .push(format!("Supplier order placement failed: {e}"));
                    return (None, RunStatus::Failed);
                }
            }
        }

        (Some(Step::FulfillmentUpdate), RunStatus::Continue)
    }
}

pub(crate) struct FulfillmentUpdateState;

impl State for FulfillmentUpdateState {
    fn name(&self) -> Step {
        Step::FulfillmentUpdate
    }

    fn do_work(
        &self,
        _mcp_addresses: Vec<String>,
        ctx: &mut ExecutionContext,
    ) -> (Option<Step>, RunStatus) {
        if let Some(prompt) = ctx.prompt_plan.prompts.get(&self.name()) {
            ctx.answers.push(prompt.clone());
        } else {
            ctx.answers
                .push("fulfillment information recorded".to_string());
        }

        (None, RunStatus::Done)
    }
}

// --- Contract state and run loop ---

#[derive(Serialize, Deserialize)]
pub struct DropshippingStepAgentContractState {
    pub mcp_contract_addresses: Vec<String>,
}

impl DropshippingStepAgentContractState {
    pub fn new(mcp_contract_addresses: Vec<String>) -> Self {
        Self { mcp_contract_addresses }
    }

    pub fn run(
        &self,
        mut context: ExecutionContext,
    ) -> (RunStatus, ExecutionContext) {
        loop {
            let Some(step) = context.step.clone() else {
                return (RunStatus::Done, context);
            };

            let handler: Box<dyn State> = match step {
                Step::CartReview => Box::new(CartReviewState),
                Step::RiskCheck => Box::new(RiskCheckState),
                Step::HumanApproval => Box::new(HumanApprovalState),
                Step::PayWithWUSD => Box::new(PayWithWusdState),
                Step::PlaceSupplierOrder => Box::new(PlaceSupplierOrderState),
                Step::FulfillmentUpdate => Box::new(FulfillmentUpdateState),
            };

            let (next_step, status) =
                handler.do_work(self.mcp_contract_addresses.clone(), &mut context);

            context.step = next_step;

            match status {
                RunStatus::Continue => continue,
                RunStatus::Pending => return (RunStatus::Pending, context),
                RunStatus::Done => return (RunStatus::Done, context),
                RunStatus::Failed => return (RunStatus::Failed, context),
            }
        }
    }
}
