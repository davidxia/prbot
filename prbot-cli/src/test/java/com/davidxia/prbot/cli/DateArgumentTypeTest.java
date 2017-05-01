package com.davidxia.prbot.cli;

import static org.hamcrest.CoreMatchers.containsString;
import static org.hamcrest.CoreMatchers.is;
import static org.junit.Assert.assertThat;
import static org.mockito.Mockito.mock;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import net.sourceforge.argparse4j.inf.Argument;
import net.sourceforge.argparse4j.inf.ArgumentParser;
import net.sourceforge.argparse4j.inf.ArgumentParserException;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.ExpectedException;

public class DateArgumentTypeTest {

  @Rule
  public ExpectedException thrown = ExpectedException.none();

  private static final String PATTERN_1 = "yyyy-MM-dd";
  private static final String SOURCE_1 = "2016-11-26";
  private static final String PATTERN_2 = "MMMM d, yyyy";
  private static final String SOURCE_2 = "January 2, 2010";
  private static final Date EXPECTED_DATE_1;
  private static final Date EXPECTED_DATE_2;
  static {
    try {
      EXPECTED_DATE_1 = new SimpleDateFormat(PATTERN_1, Locale.ENGLISH).parse(SOURCE_1);
      EXPECTED_DATE_2 = new SimpleDateFormat(PATTERN_2, Locale.ENGLISH).parse(SOURCE_2);
    } catch (ParseException e) {
      throw new AssertionError("Shouldn't happen.");
    }
  }

  @Test
  public void convert1() throws Exception {
    final DateArgumentType sut = DateArgumentType.create(PATTERN_1);
    final Date date = sut.convert(null, null, SOURCE_1);
    assertThat(date, is(EXPECTED_DATE_1));

    final DateArgumentType sut2 = DateArgumentType.create(PATTERN_2);
    final Date date2 = sut2.convert(null, null, SOURCE_2);
    assertThat(date2, is(EXPECTED_DATE_2));
  }

  @Test
  public void convertBadInput() throws Exception {
    final ArgumentParser parser = mock(ArgumentParser.class);
    final Argument arg = mock(Argument.class);
    final DateArgumentType sut = DateArgumentType.create(PATTERN_1);

    thrown.expect(ArgumentParserException.class);
    thrown.expectMessage(containsString(
        "Cannot parse date string foobar into format " + PATTERN_1));

    sut.convert(parser, arg, "foobar");
  }

}