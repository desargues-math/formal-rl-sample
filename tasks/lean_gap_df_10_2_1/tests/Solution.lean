import Submission
import Mathlib.Algebra.Module.LinearMap.Defs
import Mathlib.Algebra.Module.Submodule.Defs

/-
Let $R$ be a ring with unity, and $M, N$ be $R$-modules.
Let $\phi:M \rightarrow N$ be an $R$-module homomorphism.
Then the kernel of $\phi$ is an $R$-submodule of $M$,
and the image of $\phi$ is an $R$-submodule of $N$.
Contributor: anonymous
-/
theorem DF_10_2_1 {R : Type*} [Semiring R]
    {M N : Type*} [AddCommMonoid M] [Module R M]
    [AddCommMonoid N] [Module R N] (φ : M →ₗ[R] N) :
    (∃ S : Submodule R M, ∀ x : M, x ∈ S ↔ φ x = 0) ∧
    (∃ T : Submodule R N, ∀ y : N, y ∈ T ↔ ∃ x : M, φ x = y) := by
  exact Submission.DF_10_2_1
