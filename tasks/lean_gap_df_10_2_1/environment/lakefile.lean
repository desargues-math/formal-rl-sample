import Lake
open Lake DSL

-- The generated Annals workspaces use ordinary (non-`module`) Lean files.
package annals_challenge where
  allowNonModules := true
  leanOptions := #[⟨`autoImplicit, false⟩]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "5e0c4e5239cb0a2d86d68a884bf52cfd963fce22"

-- Uniform Mordell–Lang has no ChallengeDeps file. This library is not a
-- default target; Lake builds it only when one of the other modules imports it.
lean_lib ChallengeDeps

@[default_target] lean_lib Challenge
@[default_target] lean_lib Solution
@[default_target] lean_lib Submission
