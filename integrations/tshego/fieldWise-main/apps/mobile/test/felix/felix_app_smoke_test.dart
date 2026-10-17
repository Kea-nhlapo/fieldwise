import 'package:almanac/features/felix/felix_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Felix frontend opens and navigates its main workflow', (tester) async {
    await tester.pumpWidget(const FelixApp());

    expect(find.text('Hello, Felix'), findsOneWidget);
    expect(find.text('100'), findsOneWidget);

    await tester.tap(find.text('Farm'));
    await tester.pumpAndSettle();
    expect(find.text('Pi setups'), findsOneWidget);
    expect(find.text('Network layout'), findsOneWidget);

    await tester.tap(find.text('Insights'));
    await tester.pumpAndSettle();
    expect(find.text('Plan your day'), findsOneWidget);

    await tester.tap(find.text('Profile'));
    await tester.pumpAndSettle();
    expect(find.text('Your activity'), findsOneWidget);
  });

  testWidgets('Felix can inspect a setup and record a visit', (tester) async {
    await tester.pumpWidget(const FelixApp());

    await tester.tap(find.text('Farm'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'PI-007');
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Green Acre'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Green Acre'));
    await tester.pumpAndSettle();

    expect(find.text('PI-007'), findsWidgets);
    expect(find.text('Sample outlook'), findsOneWidget);
    await tester.ensureVisible(find.text('Add to plan'));
    await tester.tap(find.text('Add to plan'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Insights'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Record visit').first);
    await tester.tap(find.text('Record visit').first);
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile).at(0));
    await tester.tap(find.byType(CheckboxListTile).at(1));
    await tester.enterText(find.byType(TextField).last, 'No visible symptoms');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save visit'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Profile'));
    await tester.pumpAndSettle();
    expect(find.textContaining('No visible symptoms'), findsOneWidget);
  });
}
