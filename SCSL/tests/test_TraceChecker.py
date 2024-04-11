from unittest import TestCase

from SCSL.TraceChecker.tracechecker import (MonitorTreeConjunctionNode,
                                            MonitorTreeDisjunctionNode,
                                            MonitorTreeNegateNode,
                                            MonitorTreeAtomNode,
                                            MonitorTreeExpressionNode,
                                            MonitorTreeVariableNode,
                                            MonitorTreeQuantifierNode,
                                            Monitor)
from SCSL.Specifications.builder import Quantifier, forall, exists, conjunction, disjunction, negate
from SCSL.Specifications.predicates import calls


class TestMonitorTreeConjunctionNode(TestCase):

    def test_instantiation(self):
        # initialise formula
        spec = Quantifier(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: conjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise conjunction node
        conjunction_node = MonitorTreeConjunctionNode(spec, {0:0}, monitor)
        self.assertIsInstance(conjunction_node, MonitorTreeConjunctionNode)


class TestMonitorTreeQuantifierNode(TestCase):

    def test_check_satisfaction_simple_quantifier(self):
        # initialise formula
        spec = Quantifier(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: conjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0:0}, monitor)
        # initialise event
        event = {"type": "trigger"}
        # check satisfaction
        satisfied = quantifier_node.check_satisfaction(event)
        self.assertTrue(satisfied)

    def test_add_branch(self):
        # initialise formula
        spec = Quantifier(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: conjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise event
        event = {"type": "trigger", "time": 0}
        # add branch
        quantifier_node.add_branch(event)
        # assert the existence of a new branch
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # assert that the new branch's root is a conjunction
        self.assertIsInstance(quantifier_node.get_children()[0], MonitorTreeConjunctionNode)
        # assert that the binding attached to the new branch is correct
        self.assertEqual(quantifier_node.get_children()[0].get_binding(), {0:0})

    def test_trace_checking_universal_conjunction_satisfaction(self):
        # initialise formula
        spec = forall(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: conjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event
        duration_event = {"type": "measurement", "value": 5}
        # apply to nodes
        lhs_expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        lhs_expression_node.evaluate(duration_event["value"])
        rhs_expression_node = quantifier_node.get_children()[0].get_children()[1].get_children()[0]
        rhs_expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(lhs_expression_node.get_value(), 5)
        self.assertEqual(rhs_expression_node.get_value(), 5)
        # evaluate upwards from the atoms
        lhs_expression_node.evaluate_upwards()
        rhs_expression_node.evaluate_upwards()
        # assert values of atoms
        self.assertTrue(quantifier_node.get_children()[0].get_children()[0].get_value())
        self.assertTrue(quantifier_node.get_children()[0].get_children()[1].get_value())
        # assert value of conjunction
        self.assertTrue(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier - should be None
        self.assertIsNone(quantifier_node.get_value())

    def test_trace_checking_universal_conjunction_violation(self):
        # initialise formula
        spec = forall(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: conjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event
        duration_event = {"type": "measurement", "value": 30}
        # apply to nodes
        lhs_expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        lhs_expression_node.evaluate(duration_event["value"])
        rhs_expression_node = quantifier_node.get_children()[0].get_children()[1].get_children()[0]
        rhs_expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(lhs_expression_node.get_value(), 30)
        self.assertEqual(rhs_expression_node.get_value(), 30)
        # evaluate upwards from the atoms
        lhs_expression_node.evaluate_upwards()
        rhs_expression_node.evaluate_upwards()
        # assert values of atoms
        self.assertFalse(quantifier_node.get_children()[0].get_children()[0].get_value())
        self.assertFalse(quantifier_node.get_children()[0].get_children()[1].get_value())
        # assert value of conjunction
        self.assertFalse(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier
        self.assertFalse(quantifier_node.get_value())

    def test_trace_checking_universal_disjunction_satisfaction(self):
        # initialise formula
        spec = forall(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: disjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event - the value chosen here means that only one atomic constraint will be satisfied
        duration_event = {"type": "measurement", "value": 15}
        # apply to nodes
        lhs_expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        lhs_expression_node.evaluate(duration_event["value"])
        rhs_expression_node = quantifier_node.get_children()[0].get_children()[1].get_children()[0]
        rhs_expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(lhs_expression_node.get_value(), 15)
        self.assertEqual(rhs_expression_node.get_value(), 15)
        # evaluate upwards from the atoms
        lhs_expression_node.evaluate_upwards()
        rhs_expression_node.evaluate_upwards()
        # assert values of atoms
        self.assertFalse(quantifier_node.get_children()[0].get_children()[0].get_value())
        self.assertTrue(quantifier_node.get_children()[0].get_children()[1].get_value())
        # assert value of disjunction
        self.assertTrue(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier - should be None
        self.assertIsNone(quantifier_node.get_value())

    def test_trace_checking_universal_disjunction_violation(self):
        # initialise formula
        spec = forall(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: disjunction(binding, binding[0].duration() < 10, binding[0].duration() < 20)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event - the value chosen here means that only one atomic constraint will be satisfied
        duration_event = {"type": "measurement", "value": 30}
        # apply to nodes
        lhs_expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        lhs_expression_node.evaluate(duration_event["value"])
        rhs_expression_node = quantifier_node.get_children()[0].get_children()[1].get_children()[0]
        rhs_expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(lhs_expression_node.get_value(), 30)
        self.assertEqual(rhs_expression_node.get_value(), 30)
        # evaluate upwards from the atoms
        lhs_expression_node.evaluate_upwards()
        rhs_expression_node.evaluate_upwards()
        # assert values of atoms
        self.assertFalse(quantifier_node.get_children()[0].get_children()[0].get_value())
        self.assertFalse(quantifier_node.get_children()[0].get_children()[1].get_value())
        # assert value of disjunction
        self.assertFalse(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier
        self.assertFalse(quantifier_node.get_value())

    def test_trace_checking_universal_negation_satisfaction(self):
        # initialise formula
        spec = forall(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: negate(binding[0].duration() < 10)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event - the value chosen here means that only one atomic constraint will be satisfied
        duration_event = {"type": "measurement", "value": 30}
        # apply to node
        expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(expression_node.get_value(), 30)
        # evaluate upwards from the atom
        expression_node.evaluate_upwards()
        # assert values of atom
        self.assertFalse(quantifier_node.get_children()[0].get_children()[0].get_value())
        # assert value of negation
        self.assertTrue(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier - should be None
        self.assertIsNone(quantifier_node.get_value())

    def test_trace_checking_universal_negation_violation(self):
        # initialise formula
        spec = forall(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: negate(binding[0].duration() < 10)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event - the value chosen here means that only one atomic constraint will be satisfied
        duration_event = {"type": "measurement", "value": 5}
        # apply to node
        expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(expression_node.get_value(), 5)
        # evaluate upwards from the atom
        expression_node.evaluate_upwards()
        # assert values of atom
        self.assertTrue(quantifier_node.get_children()[0].get_children()[0].get_value())
        # assert value of negation
        self.assertFalse(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier
        self.assertFalse(quantifier_node.get_value())

    def test_trace_checking_existential_satisfaction(self):
        # initialise formula
        spec = exists(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: negate(binding[0].duration() < 10)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event - the value chosen here means that only one atomic constraint will be satisfied
        duration_event = {"type": "measurement", "value": 30}
        # apply to node
        expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(expression_node.get_value(), 30)
        # evaluate upwards from the atom
        expression_node.evaluate_upwards()
        # assert values of atom
        self.assertFalse(quantifier_node.get_children()[0].get_children()[0].get_value())
        # assert value of negation
        self.assertTrue(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier
        self.assertTrue(quantifier_node.get_value())

    def test_trace_checking_existential_violation(self):
        # initialise formula
        spec = exists(id=0, predicate=calls("f").during("g"), binding={}).check(
            lambda binding: negate(binding[0].duration() < 10)
        )
        # initialise monitor
        monitor = Monitor(spec)
        # initialise quantifier node
        quantifier_node = MonitorTreeQuantifierNode(spec, {0: 0}, monitor)
        # assert number of children
        self.assertEqual(len(quantifier_node.get_children()), 0)
        # initialise trigger event
        trigger_event = {"type": "trigger", "time": 0}
        # add new branch
        quantifier_node.add_branch(trigger_event)
        # assert number of children of the quantifier
        self.assertEqual(len(quantifier_node.get_children()), 1)
        # initialise duration event - the value chosen here means that only one atomic constraint will be satisfied
        duration_event = {"type": "measurement", "value": 5}
        # apply to node
        expression_node = quantifier_node.get_children()[0].get_children()[0].get_children()[0]
        expression_node.evaluate(duration_event["value"])
        # assert that their values have been updated
        self.assertEqual(expression_node.get_value(), 5)
        # evaluate upwards from the atom
        expression_node.evaluate_upwards()
        # assert values of atom
        self.assertTrue(quantifier_node.get_children()[0].get_children()[0].get_value())
        # assert value of negation
        self.assertFalse(quantifier_node.get_children()[0].get_value())
        # assert value of quantifier
        self.assertIsNone(quantifier_node.get_value())
        # resolve tree
        monitor.wrap_up()
        # assert on new quantifier value
        self.assertFalse(quantifier_node.get_value())



