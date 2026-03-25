using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression
{
    public class LogicalNegationExpression : IExpression
    {
        public IExpression Expression { get; set; }

        public LogicalNegationExpression(IExpression expression)
        {
            Expression = expression;
        }

        public DataType GetDataType()
        {
            return DataType.Float;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            Expression.Compile(symbolTable, ncs);

            var type = Expression.GetDataType();

            if (type == DataType.Int)
            {
                ncs.Add(new NCSInstruction.NOTI());
            }
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
