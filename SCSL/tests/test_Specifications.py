from unittest import TestCase

from SCSL.Specifications.builder import Quantifier, forall, exists, conjunction, disjunction, negate
from SCSL.Specifications.predicates import changes, calls, inTimeInterval
from SCSL.Specifications.constraints import ValueInConcreteStateEqualToConstant, ValueInConcreteState, signal


class TestSpecifications(TestCase):

    def test_quantifier_changes_predicate(self):
        predicate = changes("x").during("f")
        quantifier = Quantifier(id=0, predicate=predicate, binding={})
        self.assertIsInstance(quantifier, Quantifier)
        self.assertEqual(quantifier._id, 0)

    def test_quantifier_calls_predicate(self):
        predicate = calls("f1").during("f2")
        quantifier = Quantifier(id=0, predicate=predicate, binding={})
        self.assertIsInstance(quantifier, Quantifier)
        self.assertEqual(quantifier._id, 0)

    def test_quantifier_get_id(self):
        quantifier = Quantifier(id=0, predicate=changes("x").during("f"), binding={})
        quantifier_id = quantifier.get_id()
        self.assertIsInstance(quantifier_id, int)
        self.assertEqual(quantifier_id, 0)

    def test_quantifier_get_sub_expressions(self):
        quantifier = Quantifier(id=0, predicate=changes("x").during("f"), binding={})
        sub_expressions = quantifier.get_sub_expression(0)
        self.assertIsNone(sub_expressions)

    def test_quantifier_get_all_quantifiers_simple_universal(self):
        quantifier = forall(id=0, predicate=changes("x").during("f"), binding={}).check(lambda binding : None)
        quantifiers = quantifier.get_quantifiers()
        self.assertIsInstance(quantifiers, list)
        self.assertEqual(len(quantifiers), 1)

    def test_quantifier_get_all_quantifiers_nested_universal(self):
        quantifier = \
            forall(id=0, predicate=changes("x").during("f"), binding={}).\
                check(
                lambda binding : forall(
                    id=1,
                    predicate=changes("x").during("f").after(binding[0]),
                    binding={0:binding[0]}
                ).check(lambda binding : None)
            )
        quantifiers = quantifier.get_quantifiers()
        self.assertIsInstance(quantifiers, list)
        self.assertEqual(len(quantifiers), 2)
        self.assertIsInstance(quantifiers[0], forall)
        self.assertIsInstance(quantifiers[1], forall)

    def test_quantifier_get_all_quantifiers_nested_existential(self):
        quantifier = \
            forall(id=0, predicate=changes("x").during("f"), binding={}).\
                check(
                lambda binding : exists(
                    id=1,
                    predicate=changes("x").during("f").after(binding[0]),
                    binding={0:binding[0]}
                ).check(lambda binding : None)
            )
        quantifiers = quantifier.get_quantifiers()
        self.assertIsInstance(quantifiers, list)
        self.assertEqual(len(quantifiers), 2)
        self.assertIsInstance(quantifiers[0], forall)
        self.assertIsInstance(quantifiers[1], exists)

    def test_quantifier_get_atoms_simple(self):
        spec = Quantifier(id=0, predicate=changes("x").during("f"), binding={}).check(
            lambda binding : binding[0]("x").equals(10)
        )
        atoms = spec.get_atoms()
        self.assertIsInstance(atoms, list)
        self.assertIsInstance(atoms[0], ValueInConcreteStateEqualToConstant)

    def test_quantifier_get_atoms_conjunction(self):
        spec = Quantifier(id=0, predicate=changes("x").during("f"), binding={}).check(
            lambda binding : conjunction(binding, binding[0]("x").equals(10), binding[0]("x").equals(20))
        )
        atoms = spec.get_atoms()
        self.assertIsInstance(atoms, list)
        self.assertEqual(len(atoms), 2)
        self.assertIsInstance(atoms[0], ValueInConcreteStateEqualToConstant)
        self.assertIsInstance(atoms[1], ValueInConcreteStateEqualToConstant)

    def test_quantifier_get_atoms_disjunction(self):
        spec = Quantifier(id=0, predicate=changes("x").during("f"), binding={}).check(
            lambda binding : disjunction(binding, binding[0]("x").equals(10), binding[0]("x").equals(20))
        )
        atoms = spec.get_atoms()
        self.assertIsInstance(atoms, list)
        self.assertEqual(len(atoms), 2)
        self.assertIsInstance(atoms[0], ValueInConcreteStateEqualToConstant)
        self.assertIsInstance(atoms[1], ValueInConcreteStateEqualToConstant)

    def test_quantifier_get_atoms_negate(self):
        spec = Quantifier(id=0, predicate=changes("x").during("f"), binding={}).check(
            lambda binding : negate(binding[0]("x").equals(10))
        )
        atoms = spec.get_atoms()
        self.assertIsInstance(atoms, list)
        self.assertEqual(len(atoms), 1)
        self.assertIsInstance(atoms[0], ValueInConcreteStateEqualToConstant)

    def test_quantifier_get_expressions(self):
        spec = Quantifier(id=0, predicate=changes("x").during("f"), binding={}).check(
            lambda binding: binding[0]("x").equals(10)
        )
        expressions = spec.get_expressions()
        self.assertIsInstance(expressions, list)
        self.assertEqual(len(expressions), 1)
        self.assertIsInstance(expressions[0], ValueInConcreteState)

    def test_quantifier_get_all_signal_names_simple(self):
        spec = Quantifier(id=0, predicate=inTimeInterval([0, 1]), binding={}).check(
            lambda binding : signal("signal").at(binding[0]) < 1
        )
        all_signal_names = spec.get_all_signal_names()
        self.assertIsInstance(all_signal_names, list)
        self.assertEqual(len(all_signal_names), 1)
        self.assertEqual(all_signal_names, ["signal"])

    def test_quantifier_get_all_signal_names_conjunction(self):
        spec = Quantifier(id=0, predicate=inTimeInterval([0, 1]), binding={}).check(
            lambda binding : conjunction(binding, signal("signal1").at(binding[0]) < 1, signal("signal2").at(binding[0]) < 2)
        )
        all_signal_names = spec.get_all_signal_names()
        self.assertIsInstance(all_signal_names, list)
        self.assertEqual(len(all_signal_names), 2)
        self.assertIn("signal1", all_signal_names)
        self.assertIn("signal2", all_signal_names)

    def test_quantifier_get_all_signal_names_disjunction(self):
        spec = Quantifier(id=0, predicate=inTimeInterval([0, 1]), binding={}).check(
            lambda binding : disjunction(binding, signal("signal1").at(binding[0]) < 1, signal("signal2").at(binding[0]) < 2)
        )
        all_signal_names = spec.get_all_signal_names()
        self.assertIsInstance(all_signal_names, list)
        self.assertEqual(len(all_signal_names), 2)
        self.assertIn("signal1", all_signal_names)
        self.assertIn("signal2", all_signal_names)

    def test_quantifier_get_all_signal_names_negate(self):
        spec = Quantifier(id=0, predicate=inTimeInterval([0, 1]), binding={}).check(
            lambda binding : negate(signal("signal").at(binding[0]) < 1)
        )
        all_signal_names = spec.get_all_signal_names()
        self.assertIsInstance(all_signal_names, list)
        self.assertEqual(len(all_signal_names), 1)
        self.assertIn("signal", all_signal_names)

    def test_quantifier_get_function_names(self):
        spec = Quantifier(id=0, predicate=changes("x").during("f"), binding={}).check(
            lambda binding: binding[0]("x").equals(10)
        )
        function_names = spec.get_function_names()
        self.assertIsInstance(function_names, list)
        self.assertEqual(len(function_names), 1)
        self.assertEqual(function_names, ["f"])
